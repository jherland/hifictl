#!/usr/bin/env python

import pty
import os
import fcntl
import termios

from av_device import AV_Device


class Fake_SerialDevice(AV_Device):
	"""Create a local serial-port-like device that can be used to
	impersonate real devices connected to a serial port.

	This is useful for testing programs communicating with a serial
	device when the serial device is not available.
	"""

	Description = "Fake serial port device"

	def __init__(self, av_loop, name):
		AV_Device.__init__(self, av_loop, name)

		self.master, self.slave = pty.openpty()
		self._client_name = os.ttyname(self.slave)

		# Close the slave descriptor. It will be reopened by the client
		os.close(self.slave)

		# Make the master descriptor non-blocking.
		fl = fcntl.fcntl(self.master, fcntl.F_GETFL)
		fcntl.fcntl(self.master, fcntl.F_SETFL, fl | os.O_NONBLOCK)

		# Backup old term settings and setup new settings
		self.term = termios.tcgetattr(self.master)
		newterm = termios.tcgetattr(self.master)
		newterm[3] = newterm[3] & ~termios.ECHO # lflags
		termios.tcsetattr(self.master, termios.TCSAFLUSH, newterm)

		self.av_loop.add_handler(self.master, self.handle_io,
			self.av_loop.READ)

	def __del__(self):
		# Close the remaining descriptor
		termios.tcsetattr(self.master, termios.TCSAFLUSH, self.term)
		os.close(self.master)

	def fileno(self):
		return self.master

	def client_name(self):
		return self._client_name

	def handle_io(self, fd, events):
		assert fd == self.master
#		self.debug("handle_io(%i, %i)" % (fd, events))

		if events & self.av_loop.READ:
#			try:
				self.handle_read()
#			except Exception as e:
#				self.debug("handle_read(): %s" % (e))
		if events & self.av_loop.WRITE:
#			try:
				self.handle_write()
#			except Exception as e:
#				self.debug("handle_write(): %s" % (e))
		if events & self.av_loop.ERROR:
			# Ignore HUP and EIO, etc. FIXME: Is this safe?
			pass

		events &= ~(self.av_loop.READ | self.av_loop.WRITE | self.av_loop.ERROR)
		if events:
			self.debug("Unhandled events: %u" % (events))


	def handle_read(self):
		"""Attempt to read data from the PTY.

		This method should probably be overridden in subclasses.
		"""
		print os.read(self.master, 64 * 1024)

	def handle_write(self):
		"""Must be overridden in subclasses that poll for writes."""
		raise NotImplementedError


def main(args):
	import argparse

	from av_loop import AV_Loop

	parser = argparse.ArgumentParser(
		description = Fake_SerialDevice.Description)
	Fake_SerialDevice.register_args("fake", parser)

	mainloop = AV_Loop(vars(parser.parse_args(args)))
	fake = Fake_SerialDevice(mainloop, "fake")

	print "%s is listening on %s" % (
		fake.Description, fake.client_name())

	return mainloop.run()


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
