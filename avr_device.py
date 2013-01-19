#!/usr/bin/env python2

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

	# Map A/V commands to corresponding AVR command
	Commands = {
		"on":   "POWER ON",
		"off":  "POWER OFF",
		"mute": "MUTE",
		"vol+": "VOL UP",
		"vol-": "VOL DOWN",
		"vol?": "VOL DOWN", # Trigger volume display

		"surround 6ch":    "6CH/8CH",
		"surround dolby":  "DOLBY",
		"surround dts":    "DTS",
		"surround stereo": "STEREO",

		"update": None # We emit this command, but do not handle it
	}

	def __init__(self, av_loop, name):
		AV_SerialDevice.__init__(self, av_loop, name)

		for subcmd in self.Commands:
			self.av_loop.add_cmd_handler(
				"%s %s" % (self.name, subcmd), self.handle_cmd)

		self.status_handler = None

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
		"""Attempt to read a datagram from the serial port."""
		dgram_len = AVR_Datagram.full_dgram_len(dgram_spec)
		dgram = self.ser.read(dgram_len)
		if len(dgram) != dgram_len:
			raise ValueError("Incomplete datagram (got %u bytes, " \
				"expected %u bytes)" % (len(dgram), dgram_len))
		data = AVR_Datagram.parse_dgram(dgram, dgram_spec)
		status = AVR_Status.from_dgram(data)
		if self.state.update(status):
			self.debug("%s -> %s" % (status, self.state))
			if self.status_handler:
				self.status_handler(status)
			self.ready_to_write(True)

	def handle_cmd(self, cmd, rest):
		if self.state.off:
			self.debug("Discarding '%s' while AVR is off" % (cmd))
			return
		cmd = cmd.split(" ", 1)
		assert cmd[0] == self.name
		assert cmd[1] in self.Commands
		assert not rest
		avr_cmd_string = self.Commands[cmd[1]]
		if avr_cmd_string is None: # Skip if command maps to None
			return
		avr_cmd = AVR_Command(avr_cmd_string)
		dgram_spec = AVR_Datagram.PC_AVR_Command
		dgram = AVR_Datagram.build_dgram(avr_cmd.dgram(), dgram_spec)
		self.schedule_write(dgram)

		# If volume is not currently showing, we need an extra trigger
		if cmd[1] in ("vol+", "vol-") and not self.state.showing_volume:
			self.schedule_write(dgram)
			self.state.showing_volume = True


def main(args):
	import os
	import argparse

	from av_loop import AV_Loop

	parser = argparse.ArgumentParser(
		description = "Communicate with " + AVR_Device.Description)
	AVR_Device.register_args("avr", parser)

	mainloop = AV_Loop(vars(parser.parse_args(args)))
	avr = AVR_Device(mainloop, "avr")

	# Forward commands from stdin to avr
	def handle_stdin(fd, events):
		assert fd == sys.stdin.fileno()
		assert events & mainloop.READ
		cmds = os.read(sys.stdin.fileno(), 64 * 1024)
		for cmd in cmds.split("\n"):
			cmd = cmd.strip()
			if cmd:
				print " -> Received cmd '%s'" % (cmd)
				mainloop.submit_cmd(cmd)
	mainloop.add_handler(sys.stdin.fileno(), handle_stdin, mainloop.READ)

	def cmd_catch_all(empty, cmd):
		assert empty == ""
		print "*** Unknown command: '%s'" % (cmd)
	mainloop.add_cmd_handler("", cmd_catch_all)

	for arg in args:
		mainloop.submit_cmd(arg)

	print "Write AVR commands to stdin (Ctrl-C to stop me)"
	return mainloop.run()


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
