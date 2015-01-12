#!/usr/bin/env python

import sys
import time

from av_serial_device import AV_SerialDevice
from avr_command import AVR_Command
from avr_dgram import AVR_Datagram
from avr_status import AVR_Status
from avr_state import AVR_State


class AVR_Device(AV_SerialDevice):
	"""Simple wrapper for communicating with a Harman/Kardon AVR 430.

	Encapsulate RS-232 traffic to/from the Harman/Kardon AVR 430 connected
	to a serial port.
	"""

	Description = "Harman/Kardon AVR 430"

	DefaultBaudRate = 38400

	def _toggle_standby(self):
		return "POWER ON" if self.state.standby else "POWER OFF"

	def _adjust_volume(self, amount=0):
		up = amount > 0
		amount = abs(amount)
		# If volume is not currently showing, we need an extra trigger
		if not self.state.showing_volume:
			amount += 1
			self.state.showing_volume = True
		return ["VOL UP" if up else "VOL DOWN"] * amount

	def _adjust_digital(self, amount=0):
		up = amount > 0
		amount = abs(amount)
		# If digital is not currently showing, we need to trigger it
###		if not self.state.showing_digital:
		yield "DIGITAL"
###			self.state.showing_digital = True
		for _ in range(amount):
			yield "DIGITAL UP" if up else "DIGITAL DOWN"

	# Map A/V commands to methods returning AVR commands
	Commands = {
		"on": lambda self: ["POWER ON"],
		"off": lambda self: ["POWER OFF"],
		"on_off": _toggle_standby, # Toggle on/off

		"mute": lambda self: ["MUTE"],
		"vol+": lambda self: self._adjust_volume(+1),
		"vol-": lambda self: self._adjust_volume(-1),
		"vol?": lambda self: self._adjust_volume(0), # Trigger volume display

		"source vid1": lambda self: ["VID1"],
		"source vid2": lambda self: ["VID2"],

		"surround 6ch": lambda self: ["6CH/8CH"],
		"surround dolby": lambda self: ["DOLBY"],
		"surround dts": lambda self: ["DTS"],
		"surround stereo": lambda self: ["STEREO"],

		"dig+": lambda self: self._adjust_digital(+1),
		"dig-": lambda self: self._adjust_digital(-1),

		"update": lambda self: [] # We only _emit_ this command
	}

	def __init__(self, av_loop, name):
		AV_SerialDevice.__init__(self, av_loop, name)

		for subcmd in self.Commands:
			self.av_loop.add_cmd_handler(
				"%s %s" % (self.name, subcmd), self.handle_cmd)

		self.status_handler = None

		self.readbuf = bytes()

		# Don't start writing until a status update is received.
		self.write_ready = False

		# Write enabling needs to be delayed. See ready_to_write()
		self.write_timer = None # or (timeout_handle, deadline)

		self.state = AVR_State(self.name, self.av_loop)

	def _delayed_ready(self):
		self.write_timer = None
		AV_SerialDevice.ready_to_write(self, True)

	def _setup_write_timer(self, deadline):
		if self.write_timer: # Disable existing timer
			self.av_loop.remove_timeout(self.write_timer[0])
		self.write_timer = (
			self.av_loop.add_timeout(deadline, self._delayed_ready),
			deadline)

	def ready_to_write(self, assign = None):
		if assign is None:
			if self.state.off:
				return False
			return AV_SerialDevice.ready_to_write(self)

		# assign == False indicates that we've just written to the AVR.
		# In that case, we should nominally delay the next write for
		# about a second.
		#
		# assign == True indicates that we've just received an updated
		# status from the AVR. In that case, we can reduce the
		# remaining time-to-next-write down to about a quarter second
		# (value determined by unscientific experiments).
		deadline = time.time() + (assign and 0.25 or 1.0)
		if assign == False: # Disable writes for 1.0s
			self.write_ready = False # Disable writes immediately
			self._setup_write_timer(deadline)
		elif assign == True: # Shorten write_timeout
			if self.write_timer and deadline > self.write_timer[1]:
				pass # Keep current timer
			elif self.write_timer or not self.write_ready:
				# Shorten existing timer or setup new timer
				self._setup_write_timer(deadline)

	def handle_read(self, dgram_spec = AVR_Datagram.AVR_PC_Status):
		"""Attempt to read a datagram from the serial port.

		Look for a bytes matching AVR_Datagram.expect_dgram_start(),
		and read additional bytes until we have a byte sequence of
		total length == AVR_Datagram.full_dgram_len().
		"""
		d_start = AVR_Datagram.expect_dgram_start(dgram_spec)
		assert isinstance(d_start, bytes)
		d_len = AVR_Datagram.full_dgram_len(dgram_spec)
		assert len(d_start) < d_len

		assert len(self.readbuf) < d_len
#		self.debug("Have %u bytes" % (len(self.readbuf)))
		self.readbuf += self.ser.read(d_len - len(self.readbuf))
		if len(self.readbuf) < d_len:
#			self.debug("Incomplete dgram (got %u/%u bytes): %s" % (
#			            len(self.readbuf), d_len,
#			            self.human_readable(self.readbuf)))
			return

		# Find start of datagram
		i = self.readbuf.find(d_start)
		if i < 0: # beyond len(self.readbuf) - len(d_start)
#			self.debug("No start of dgram in %u bytes: %s" % (
#				len(self.readbuf),
#				self.human_readable(self.readbuf)))
			self.readbuf = self.readbuf[-(len(d_start) - 1):]
			return
		elif i > 0: # dgram starts at index i
#			self.debug("dgram starts at index %u in %s" % (i,
#				self.human_readable(self.readbuf)))
			self.readbuf = self.readbuf[i:]
		assert self.readbuf.startswith(d_start)

		if len(self.readbuf) < d_len:
			return

#		self.debug("parsing self.readbuf: %s" % (
#			self.human_readable(self.readbuf)))
		dgram, self.readbuf = self.readbuf[:d_len], self.readbuf[d_len:]
		assert isinstance(dgram, bytes)
		data = AVR_Datagram.parse_dgram(dgram, dgram_spec)
		status = AVR_Status.from_dgram(data)
		if self.state.update(status):
			self.debug("%s\n\t\t-> %s" % (status, self.state))
			if self.status_handler:
				self.status_handler(status)
			self.ready_to_write(True)

	def handle_cmd(self, cmd, rest):
		if self.state.off:
			self.debug("Discarding '%s' while AVR is off" % (cmd))
			return
		self.debug("Handling '%s'" % (cmd))
		avr, cmd = cmd.split(" ", 1)
		assert avr == self.name
		assert cmd in self.Commands
		assert not rest
		command = self.Commands[cmd]
		assert callable(command)
		for command_str in command(self):
			avr_cmd = AVR_Command(avr_cmd_string)
			dgram_spec = AVR_Datagram.PC_AVR_Command
			dgram = AVR_Datagram.build_dgram(avr_cmd.dgram(), dgram_spec)
			self.schedule_write(dgram)


def main(args):
	import os
	import argparse
	from tornado.ioloop import IOLoop

	from av_loop import AV_Loop

	parser = argparse.ArgumentParser(
		description = "Communicate with " + AVR_Device.Description)
	AVR_Device.register_args("avr", parser)

	IOLoop.configure(AV_Loop, parsed_args = vars(parser.parse_args(args)))
	mainloop = IOLoop.instance()
	avr = AVR_Device(mainloop, "avr")

	# Forward commands from stdin to avr
	def handle_stdin(fd, events):
		assert fd == sys.stdin.fileno()
		assert events & mainloop.READ
		cmds = os.read(sys.stdin.fileno(), 64 * 1024)
		for cmd in cmds.split("\n"):
			cmd = cmd.strip()
			if cmd:
				print(" -> Received cmd '%s'" % (cmd))
				mainloop.submit_cmd(cmd)
	mainloop.add_handler(sys.stdin.fileno(), handle_stdin, mainloop.READ)

	def cmd_catch_all(empty, cmd):
		assert empty == ""
		print("*** Unknown command: '%s'" % (cmd))
	mainloop.add_cmd_handler("", cmd_catch_all)

	for arg in args:
		mainloop.submit_cmd(arg)

	print("Write AVR commands to stdin (Ctrl-C to stop me)")
	return mainloop.run()


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
