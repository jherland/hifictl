#!/usr/bin/env python2

import sys
import serial
import select

from av_device import AV_Device
from avr_command import AVR_Command
from avr_dgram import AVR_Datagram
from avr_status import AVR_Status


class AVR_Device(AV_Device):
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

	def __init__(self, cmd_namespace = "avr",
	             tty = "/dev/ttyUSB0", baudrate = 38400):
		AV_Device.__init__(self, cmd_namespace)

		# It seems pyserial needs the rtscts flag toggled in
		# order to communicate consistently with the remote end.
		self.ser = serial.Serial(tty, baudrate, rtscts = True)
		self.ser.rtscts = False
		self.ser.timeout = 0 # Non-blocking reads

		self.epoll = None
		self.epoll_events = select.EPOLLIN | select.EPOLLPRI \
			| select.EPOLLERR | select.EPOLLHUP

		self._next_write = sys.maxint
		self.write_queue = []

		self.status = None

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
			except Exception as e:
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

	def handle_cmd(self, cmd, ts = 0):
		if cmd not in self.Commands:
			self.debug(ts, "Unknown command: '%s'" % (cmd))
			return
		avr_cmd = AVR_Command(self.Commands[cmd])
		dgram_spec = AVR_Datagram.PC_AVR_Command
		dgram = AVR_Datagram.build_dgram(avr_cmd.dgram(), dgram_spec)
		self.schedule_write(ts, dgram)

	def ready_to_write(self, ts = 0, set_to = None):
		if set_to is not None:
			# set_to == False indicates that we've just written to
			# the AVR. In that case, we should nominally delay the
			# next write for about a second.
			# set_to == True indicates that we've just received an
			# updated status from the AVR. In that case, the AVR is
			# nominally ready to receive the next write much faster,
			# experiments show about 0.2 sec.
			self._next_write = ts + (set_to and 0.2 or 1.0)
		return ts > self._next_write

	def handle_read(self, ts, dgram_spec = AVR_Datagram.AVR_PC_Status):
		"""Attempt to read a datagram from the serial port."""
		dgram_len = AVR_Datagram.full_dgram_len(dgram_spec)
		dgram = self.ser.read(dgram_len)
		if len(dgram) != dgram_len:
			raise ValueError("Incomplete datagram (got %u bytes, " \
				"expected %u bytes)" % (len(dgram), dgram_len))
		data = AVR_Datagram.parse_dgram(dgram, dgram_spec)
		status = AVR_Status.from_dgram(data)
		if status != self.status:
			self.status = status
			self.ready_to_write(ts, True)
			self.debug(ts, status)
			return status

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


def main(args):
	import os
	import time

	epoll = select.epoll()

	avr = AVR_Device(tty = "/dev/ttyUSB1")
	avr.register(epoll)

	# Forward commands from stdin to avr
	epoll.register(sys.stdin.fileno(), select.EPOLLIN | select.EPOLLET)

	for arg in args:
		avr.handle_cmd(arg)

	t_start = time.time()
	ts = 0
	try:
		while True:
			for fd, events in epoll.poll():
				ts = time.time() - t_start
				if fd == avr.ser.fileno():
					avr.handle_events(epoll, events, ts)
				# Forward commands from stdin to avr
				elif fd == sys.stdin.fileno():
					cmds = os.read(sys.stdin.fileno(), 1024)
					for cmd in cmds.split("\n"):
						cmd = cmd.strip()
						if cmd:
							avr.handle_cmd(cmd, ts)
	except KeyboardInterrupt:
		print "Aborted by user"

	epoll.close()
	return 0


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
