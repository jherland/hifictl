#!/usr/bin/env python2

import serial
import select

from av_device import AV_Device


class HDMI_Switch(AV_Device):
	"""Simple wrapper for communicating with an HDMI switch.

	Encapsulate RS-232 commands being sent to a Marmitek Connect411 HDMI
	switch connected to a serial port.
	"""

	Description = "Marmitek Connect411 HDMI switch"

	# Marmitek has strange newline conventions
	LF = "\n\r"

	# Map A/V command to corresponding HDMI switch command
	Commands = {
		"1":       LF + "1" + LF,
		"2":       LF + "2" + LF,
		"3":       LF + "3" + LF,
		"4":       LF + "4" + LF,
		"on":      LF + "5" + LF,
		"off":     LF + "5" + LF,
		"version": LF + "v" + LF,
		"help":    LF + "?" + LF,
	}

	Init_Input = "Marmitek BV, The Netherlands. All rights reserved. " \
	             "www.marmitek.com" + LF + ">"

	def __init__(self, cmd_namespace = "hdmi",
	             tty = "/dev/ttyUSB0", baudrate = 19200):
		AV_Device.__init__(self, cmd_namespace)

		# It seems pyserial needs the rtscts flag toggled in order to
		# communicate consistently with the remote end.
		self.ser = serial.Serial(tty, baudrate, rtscts = True)
		self.ser.rtscts = False
		self.ser.timeout = 0 # Non-blocking reads

		self.epoll = None
		self.epoll_events = select.EPOLLIN | select.EPOLLPRI \
			| select.EPOLLERR | select.EPOLLHUP

		self.write_ready = True
		self.write_queue = []

	def register(self, epoll, cmd_dispatcher = None):
		self.epoll = epoll
		self.epoll.register(self.ser.fileno(), self.epoll_events)
		return self.ser.fileno()

	def handle_events(self, epoll, events, ts = 0):
		ret = None
		assert epoll == self.epoll
		if events & select.EPOLLIN:
			ret = self.handle_read(self.ser.read(1024), ts)
		if events & select.EPOLLOUT:
			self.handle_write(ts)
		events &= ~(select.EPOLLIN | select.EPOLLOUT)
		if events:
			self.debug(ts, "Unhandled events: %u" % (events))
		return ret

	def handle_cmd(self, cmd, ts = 0):
		if cmd not in self.Commands:
			self.debug(ts, "Unknown command: '%s'" % (cmd))
			return
		self.debug(ts, "Adding '%s' to write queue..." % (cmd))
		if not self.write_queue:
			self.epoll.modify(self.ser.fileno(),
			                  self.epoll_events | select.EPOLLOUT)
		self.write_queue.append(self.Commands[cmd])

	def handle_read(self, s, ts):
		if s == self.Init_Input:
			self.debug(ts, "started.")
			self.on() # Trigger wake from standby
		elif s == "\0":
			self.debug(ts, "stopped.")
		elif s.strip() in ("1", "2", "3", "4", "5", "v", "?"):
			self.debug(ts, "Executed command '%s'" % (s.strip()))
		elif s != ">":
			self.debug(ts, "Unrecognized input: '%s'" % (
				self.human_readable(s)))

		if s.endswith(">"):
			self.write_ready = True
			self.debug(ts, "ready.")

		return s.replace("\r", "").strip()

	def handle_write(self, ts):
		if not self.write_ready:
			return
		cmd = self.write_queue.pop(0)
		written = self.ser.write(cmd)
		assert written == len(cmd)
		self.debug(ts, "Wrote command '%s'" % (self.human_readable(cmd)))
		self.write_ready = False
		if not self.write_queue:
			self.epoll.modify(self.ser.fileno(), self.epoll_events)

	def on(self):
		self.handle_cmd("on")

	def off(self):
		self.handle_cmd("off")

	def switch(self, port):
		assert port in ("1", "2", "3", "4")
		self.handle_cmd(port)

	def version(self):
		self.handle_cmd("version")

	def help(self):
		self.handle_cmd("help")


def main(args):
	if not args:
		args = ["version"]

	hs = HDMI_Switch()
	epoll = select.epoll()
	hs.register(epoll)
	for arg in args:
		hs.handle_cmd(arg)
	while hs.write_queue or not hs.write_ready:
		for fd, events in epoll.poll():
			assert fd == hs.ser.fileno()
			data = hs.handle_events(epoll, events)
			if data:
				print data,
				if not data.endswith(">"):
					print

	epoll.close()
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
