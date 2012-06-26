#!/usr/bin/env python2

import serial

from av_device import AV_Device


class AV_SerialDevice(AV_Device):
	"""Simple wrapper for communicating with a device connected to a tty.

	Encapsulate RS-232 traffic to/from an A/V device connected to a serial
	port.
	"""

	Description = "Unspecified A/V device connected to serial port"

	@staticmethod
	def human_readable(s):
		"""Convenience method for making byte strings human-readable.

		Returns the given string with all non-human-readable chars
		replaced by their respective hax code (formatted as \0x##).
		"""
		ret = ""
		for c in s:
			i = ord(c)
			if i >= 0x20 and i < 0x7f:
				ret += c
			else:
				ret += "\\0x%02x" % (ord(c))
		return ret

	def __init__(self, av_loop, name, tty, baudrate):
		AV_Device.__init__(self, av_loop, name)

		# It seems pyserial needs the rtscts flag toggled in
		# order to communicate consistently with the remote end.
		self.ser = serial.Serial(tty, baudrate, rtscts = True)
		self.ser.rtscts = False
		self.ser.timeout = 0 # Non-blocking reads

		self.write_queue = []
		self.write_ready = True

		self.av_loop.add_handler(self.ser.fileno(), self.handle_io,
			self.av_loop.READ)

	def handle_io(self, fd, events):
		assert fd == self.ser.fileno()
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

		events &= ~(self.av_loop.READ | self.av_loop.WRITE)
		if events:
			self.debug("Unhandled events: %u" % (events))

	def ready_to_write(self, set_to = None):
		"""Return whether or not the remote end is ready to receive.

		This method should probably be extended in subclasses."""
		if set_to is not None:
			self.write_ready = set_to

		ret = self.write_ready and self.write_queue
		eventmask = self.av_loop.READ
		if ret:
			eventmask |= self.av_loop.WRITE
		self.av_loop.update_handler(self.ser.fileno(), eventmask)
		return ret

	def handle_read(self):
		"""Attempt to read data from the serial port.

		This method should probably be overridden in subclasses.
		"""
		print self.human_readable(self.ser.read(64 * 1024))

	def handle_write(self):
		"""Attempt to write data to the serial port."""
		if self.ready_to_write():
			data = self.write_queue.pop(0)
			written = self.ser.write(data)
			assert written == len(data)
			self.ready_to_write(False)
			self.debug("Wrote %u bytes (%s)" % (written,
				" ".join(["%02x" % (ord(b)) for b in data])))

	def schedule_write(self, data):
		self.debug("Adding %u bytes to write queue (%s)" % (len(data),
			" ".join(["%02x" % (ord(b)) for b in data])))
		self.write_queue.append(data)
		self.ready_to_write()
