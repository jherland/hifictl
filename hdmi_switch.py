#!/usr/bin/env python

import sys

from av_serial_device import AV_SerialDevice


class HDMI_Switch(AV_SerialDevice):
	"""Simple wrapper for communicating with an HDMI switch.

	Encapsulate RS-232 commands being sent to a Marmitek Connect411 HDMI
	switch connected to a serial port.
	"""

	Description = "Marmitek Connect411 HDMI switch"

	DefaultBaudRate = 19200

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

	def __init__(self, av_loop, name):
		AV_SerialDevice.__init__(self, av_loop, name)

		self.input_handler = None

		for subcmd in self.Commands:
			self.av_loop.add_cmd_handler(
				"%s %s" % (self.name, subcmd), self.handle_cmd)

	def handle_read(self):
		s = self.ser.read(64 * 1024)
		if s == self.Init_Input:
			self.debug("started.")
			# Trigger wake from standby
			self.handle_cmd(self.name + " on", "")
		elif s == "\0":
			self.ready_to_write(False)
			self.debug("stopped.")
		elif s.strip() in ("1", "2", "3", "4", "5", "v", "?"):
			self.debug("Executed command '%s'" % (s.strip()))
		elif s != ">":
			self.debug("Unrecognized input: '%s'" % (
				self.human_readable(s)))

		if s.endswith(">"):
			self.ready_to_write(True)
			self.debug("ready.")

		if self.input_handler:
			self.input_handler(s.replace("\r", "").strip())

	def handle_cmd(self, cmd, rest):
		cmd = cmd.split()
		assert cmd[0] == self.name
		assert len(cmd) == 2
		self.schedule_write(self.Commands[cmd[1]])


def main(args):
	import os
	import argparse
	from tornado.ioloop import IOLoop

	from av_loop import AV_Loop

	parser = argparse.ArgumentParser(
		description = "Communicate with " + HDMI_Switch.Description)
	HDMI_Switch.register_args("hdmi", parser)

	IOLoop.configure(AV_Loop, parsed_args = vars(parser.parse_args(args)))
	mainloop = IOLoop.instance()
	hdmi = HDMI_Switch(mainloop, "hdmi")

	def print_serial_data(data):
		if data:
			print(data, end=' ')
			if not data.endswith(">"):
				print()
	hdmi.input_handler = print_serial_data

	# Forward commands from stdin to avr
	def handle_stdin(fd, events):
		assert fd == sys.stdin.fileno()
		assert events & mainloop.READ
		cmds = os.read(sys.stdin.fileno(), 64 * 1024)
		for cmd in cmds.split("\n"):
			cmd = cmd.strip()
			if cmd:
				print(" -> Received cmd '%s'" % (cmd))
				mainloop.submit_cmd(cmd)
	mainloop.add_handler(sys.stdin.fileno(), handle_stdin, mainloop.READ)

	def cmd_catch_all(empty, cmd):
		assert empty == ""
		print("*** Unknown command: '%s'" % (cmd))
	mainloop.add_cmd_handler("", cmd_catch_all)

	for arg in args:
		mainloop.submit_cmd(arg)

	print("Write HDMI switch commands to stdin (Ctrl-C to stop me)")
	return mainloop.run()


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
