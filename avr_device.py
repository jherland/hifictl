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

	# Map A/V commands to corresponding AVR command
	Commands = {
		"on":   "POWER ON",
		"off":  "POWER OFF",
		"mute": "MUTE",
		"vol+": "VOL UP",
		"vol-": "VOL DOWN",
	}

	def __init__(self, av_loop, name = "avr",
			tty = "/dev/ttyUSB0", baudrate = 38400):
		AV_SerialDevice.__init__(self, av_loop, name, tty, baudrate)

		self.av_loop.add_cmd_handler(self.name, self.handle_cmd)

		self.status_handler = None

		# Don't start writing until a status update is received.
		self.write_ready = False

		# Write enabling needs to be delayed. See ready_to_write()
		self.write_timer = None # or (timeout_handle, deadline)

		self.state = AVR_State(self.name, self.handle_cmd)

	def _delayed_ready(self):
		self.write_timer = None
		AV_SerialDevice.ready_to_write(self, True)

	def _setup_write_timer(self, deadline):
		if self.write_timer: # Disable existing timer
			self.av_loop.remove_timeout(self.write_timer[0])
		self.write_timer = (
			self.av_loop.add_timeout(deadline, self._delayed_ready),
			deadline)

	def ready_to_write(self, set_to = None):
		if set_to is None:
			return AV_SerialDevice.ready_to_write(self)

		# set_to == False indicates that we've just written to the AVR.
		# In that case, we should nominally delay the next write for
		# about 1.0s.
		#
		# set_to == True indicates that we've just received an updated
		# status from the AVR. In that case, we can reduce the
		# remaining time-to-next-write down to about 0.2s
		# (value determined by unscientific experiments)
		deadline = time.time() + (set_to and 0.2 or 1.0)
		if set_to == False: # Disable writes for 1.0s
			self.write_ready = False # Disable writes immediately
			self._setup_write_timer(deadline)
		elif set_to == True: # Shorten write_timeout to 0.2s
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
		if self.state.update(time.time() - self.av_loop.t0, status):
			self.debug(status)
			if self.status_handler:
				self.status_handler(status)
			self.ready_to_write(True)

	def handle_cmd(self, namespace, cmd):
		assert namespace == self.name
		if cmd not in self.Commands:
			self.debug("Unknown command: '%s'" % (cmd))
			return
		avr_cmd = AVR_Command(self.Commands[cmd])
		dgram_spec = AVR_Datagram.PC_AVR_Command
		dgram = AVR_Datagram.build_dgram(avr_cmd.dgram(), dgram_spec)
		self.schedule_write(dgram)


def main(args):
	import os

	from av_loop import AV_Loop

	mainloop = AV_Loop()

	avr = AVR_Device(mainloop, tty = "/dev/ttyUSB1")

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

	def cmd_dispatcher(namespace, subcmd):
		print "*** Unknown command: '%s %s'" % (namespace, subcmd)
	mainloop.add_cmd_handler("", cmd_dispatcher)

	for arg in args:
		mainloop.submit_cmd(arg)

	print "Write AVR commands to stdin (Ctrl-C to stop me)"
	return mainloop.run()


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
