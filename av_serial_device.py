#!/usr/bin/env python

import serial

from av_device import AV_Device


class AV_SerialDevice(AV_Device):
	"""Simple wrapper for communicating with a device connected to a tty.

	Encapsulate RS-232 traffic to/from an A/V device connected to a serial
	port.
	"""

	Description = "Unspecified A/V device connected to serial port"

	DefaultTTY = "/dev/ttyUSB0"

	DefaultBaudRate = 9600

	@staticmethod
	def human_readable(s):
		"""Convenience method for making byte strings human-readable.

		Returns the given string with all non-human-readable chars
		replaced by their respective hax code (formatted as \0x##).
		"""
		ret = ""
		for c in s:
			if c >= 0x20 and c < 0x7f:
				ret += chr(c)
			else:
				ret += "\\0x%02x" % (c)
		return ret

	@classmethod
	def register_args(cls, name, arg_parser):
		arg_parser.add_argument("--%s-tty" % (name),
			default = cls.DefaultTTY,
			help = "Path to serial port connected to %s"
				" (default: %%(default)s)" % (cls.Description),
			metavar = "TTY")
		arg_parser.add_argument("--%s-baud" % (name),
			default = cls.DefaultBaudRate,
			help = "Serial port baud rate for %s"
				" (default: %%(default)s)" % (cls.Description),
			metavar = "BPS")

	def __init__(self, av_loop, name):
		AV_Device.__init__(self, av_loop, name)

		tty = av_loop.args["%s_tty" % (name)]
		baudrate = int(av_loop.args["%s_baud" % (name)])

		# It seems pyserial needs the rtscts flag toggled in
		# order to communicate consistently with the remote end.
		self.ser = serial.Serial(tty, baudrate, rtscts = True)
		self.ser.rtscts = False
		self.ser.timeout = 0 # Non-blocking reads

		self.write_queue = []
		self.write_ready = True

		self.av_loop.add_handler(self.ser.fileno(), self.handle_io,
			self.av_loop.READ)
		self.check_writable = False

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

	def ready_to_write(self, assign = None):
		"""Return whether or not the remote end is ready to receive.

		This method should probably be extended in subclasses."""
		if assign is not None:
			self.write_ready = assign

		ret = self.write_ready and self.write_queue

		events = self.av_loop.READ
		check_writable = False
		if ret:
			events |= self.av_loop.WRITE
			check_writable = True

		if check_writable != self.check_writable:
			self.av_loop.update_handler(self.ser.fileno(), events)
			self.check_writable = check_writable
		return ret

	def handle_read(self):
		"""Attempt to read data from the serial port.

		This method should probably be overridden in subclasses.
		"""
		print(self.human_readable(self.ser.read(64 * 1024)))

	def handle_write(self):
		"""Attempt to write data to the serial port."""
		if self.ready_to_write():
			data = self.write_queue.pop(0)
			written = self.ser.write(data)
			assert written == len(data)
			self.debug("Wrote %u bytes (%s)" % (written,
				" ".join(["%02x" % (b) for b in data])))
			self.ready_to_write(False)

	def schedule_write(self, data):
		self.debug("Adding %u bytes to write queue (%s)" % (len(data),
			" ".join(["%02x" % (b) for b in data])))
		self.write_queue.append(data)
		self.ready_to_write()
