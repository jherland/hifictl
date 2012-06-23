#!/usr/bin/env python2

import sys
import os
import serial
import select
import time

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
		"on":   AVR_Command("POWER ON"),
		"off":  AVR_Command("POWER OFF"),
		"mute": AVR_Command("MUTE"),
		"vol+": AVR_Command("VOL UP"),
		"vol-": AVR_Command("VOL DOWN"),
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

		self.next_write = sys.maxint
		self.write_queue = []

		self.status = None

	def register(self, epoll, cmd_dispatcher = None):
		self.epoll = epoll
		self.epoll.register(self.ser.fileno(), self.epoll_events)
		return self.ser.fileno()

	def handle_events(self, epoll, events, ts = 0):
		assert epoll == self.epoll
		if events & select.EPOLLIN:
			try:
				dgram = self.handle_read()
				status = AVR_Status.from_dgram(dgram)
				if status != self.status:
					self.status = status
					# Ready to receive next write in 0.2
					# sec. (value found experimentally...)
					self.next_write = ts + 0.2
					self.debug(ts, status)
			except Exception as e:
				self.debug(ts, "handle_read(): %s" % (e))

		if events & select.EPOLLOUT:
			try:
				if not self.handle_write(ts):
					self.epoll.modify(self.ser.fileno(),
						self.epoll_events)
			except Exception as e:
				self.debug(ts, "handle_write(): %s" % (e))

		events &= ~(select.EPOLLIN | select.EPOLLOUT)
		if events:
			self.debug(ts, "Unhandled events: %u" % (events))

	def handle_cmd(self, cmd, ts = 0):
		if cmd not in self.Commands:
			self.debug(ts, "Unknown command: '%s'" % (cmd))
			return
		self.debug(ts, "Adding '%s' to write queue..." % (cmd))
		if not self.enqueue_dgram(self.Commands[cmd].dgram()):
			self.epoll.modify(self.ser.fileno(),
				self.epoll_events | select.EPOLLOUT)

	def handle_read(self, dgram_spec = None):
		"""Attempt to read a datagram from the serial port."""
		if dgram_spec is None:
			dgram_spec = AVR_Datagram.AVR_PC_Status
		dgram_len = AVR_Datagram.full_dgram_len(dgram_spec)
		dgram = self.ser.read(dgram_len)
		if len(dgram) != dgram_len:
			raise ValueError("Incomplete datagram (got %u bytes, " \
				"expected %u bytes)" % (len(dgram), dgram_len))
		ret = AVR_Datagram.parse_dgram(dgram, dgram_spec)
		return ret

	def handle_write(self, ts):
		"""Attempt to write a datagram to the serial port."""
		if self.write_queue and ts > self.next_write:
			dgram = self.write_queue.pop(0)
			written = self.ser.write(dgram)
			assert written == len(dgram)
			# Nominally wait 1 sec. before sending next write, but
			# will be shortened if AVR status changes
			# (see self.handle_events()).
			self.next_write = ts + 1
			self.debug(ts, "Wrote '%s'" % (" ".join(["%02x" % (ord(b)) for b in dgram]))) ### REMOVEME
		return len(self.write_queue)

	def enqueue_dgram(self, data, dgram_spec = None):
		"""Send the given data according to the given datagram spec."""
		if dgram_spec is None:
			dgram_spec = AVR_Datagram.PC_AVR_Command
		dgram = AVR_Datagram.build_dgram(data, dgram_spec)
		self.write_queue.append(dgram)
		return len(self.write_queue) - 1


def main(args):
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
