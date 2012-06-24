#!/usr/bin/env python2

import sys
import serial
import select

from av_serial_device import AV_SerialDevice


class HDMI_Switch(AV_SerialDevice):
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
		AV_SerialDevice.__init__(self, cmd_namespace, tty, baudrate)

		self._write_ready = True

	def handle_cmd(self, cmd, ts = 0):
		if cmd not in self.Commands:
			self.debug(ts, "Unknown command: '%s'" % (cmd))
			return
		self.schedule_write(ts, self.Commands[cmd])

	def ready_to_write(self, ts = 0, set_to = None):
		if set_to is not None:
			self._write_ready = set_to
		return self._write_ready

	def handle_read(self, ts):
		s = self.ser.read(1024)
		if s == self.Init_Input:
			self.debug(ts, "started.")
			self.handle_cmd("on", ts) # Trigger wake from standby
		elif s == "\0":
			self.debug(ts, "stopped.")
		elif s.strip() in ("1", "2", "3", "4", "5", "v", "?"):
			self.debug(ts, "Executed command '%s'" % (s.strip()))
		elif s != ">":
			self.debug(ts, "Unrecognized input: '%s'" % (
				self.human_readable(s)))

		if s.endswith(">"):
			self.ready_to_write(ts, True)
			self.debug(ts, "ready.")

		return s.replace("\r", "").strip()


def main(args):
	import os
	import time

	epoll = select.epoll()

	hs = HDMI_Switch()
	hs.register(epoll)

	# Forward commands from stdin to avr
	epoll.register(sys.stdin.fileno(), select.EPOLLIN | select.EPOLLET)

	for arg in args:
		hs.handle_cmd(arg)

	t_start = time.time()
	ts = 0
	try:
		while True:
			for fd, events in epoll.poll():
				ts = time.time() - t_start
				if fd == hs.ser.fileno():
					data = hs.handle_events(epoll, events)
					if data:
						print data,
						if not data.endswith(">"):
							print
				# Forward commands from stding to hdmi switch
				elif fd == sys.stdin.fileno():
					cmds = os.read(sys.stdin.fileno(), 1024)
					for cmd in cmds.split("\n"):
						cmd = cmd.strip()
						if cmd:
							hs.handle_cmd(cmd, ts)
	except KeyboardInterrupt:
		print "Aborted by user"

	epoll.close()
	return 0


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
