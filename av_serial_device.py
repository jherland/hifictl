#!/usr/bin/env python2

import sys
import serial
import select

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

	def __init__(self, cmd_namespace, tty, baudrate):
		AV_Device.__init__(self, cmd_namespace)

		# It seems pyserial needs the rtscts flag toggled in
		# order to communicate consistently with the remote end.
		self.ser = serial.Serial(tty, baudrate, rtscts = True)
		self.ser.rtscts = False
		self.ser.timeout = 0 # Non-blocking reads

		self.epoll = None
		self.epoll_events = select.EPOLLIN | select.EPOLLPRI \
			| select.EPOLLERR | select.EPOLLHUP

		self.write_queue = []

	def register(self, epoll, cmd_dispatcher = None):
		self.epoll = epoll
		self.epoll.register(self.ser.fileno(), self.epoll_events)
		return self.ser.fileno()

	def handle_events(self, epoll, events, ts = 0):
		ret = None
		assert epoll == self.epoll
		if events & select.EPOLLIN:
			try:
				ret = self.handle_read(ts)
			except ValueError as e:
				self.debug(ts, "handle_read(): %s" % (e))
		if events & select.EPOLLOUT:
			try:
				if not self.handle_write(ts):
					# Nothing more to write, reset eventmask
					self.epoll.modify(self.ser.fileno(),
						self.epoll_events)
			except Exception as e:
				self.debug(ts, "handle_write(): %s" % (e))

		events &= ~(select.EPOLLIN | select.EPOLLOUT)
		if events:
			self.debug(ts, "Unhandled events: %u" % (events))
		return ret

	def ready_to_write(self, ts = 0, set_to = None):
		"""Return whether or not the remote end is ready to receive.

		This method should probably be overridden in subclasses."""
		return ts > 0.5

	def handle_read(self, ts):
		"""Attempt to read a datagram from the serial port.

		This method should probably be overridden in subclasses.
		"""
		return self.human_readable(self.ser.read(1024))

	def handle_write(self, ts):
		"""Attempt to write a datagram to the serial port."""
		if self.write_queue and self.ready_to_write(ts):
			data = self.write_queue.pop(0)
			written = self.ser.write(data)
			assert written == len(data)
			self.ready_to_write(ts, False)
			self.debug(ts, "Wrote %u bytes (%s)" % (written,
				" ".join(["%02x" % (ord(b)) for b in data])))
		return len(self.write_queue)

	def schedule_write(self, ts, data):
		self.debug(ts, "Adding %u bytes to write queue (%s)" % (
			len(data), " ".join(["%02x" % (ord(b)) for b in data])))
		if not self.write_queue:
			self.epoll.modify(self.ser.fileno(),
				self.epoll_events | select.EPOLLOUT)
		self.write_queue.append(data)
