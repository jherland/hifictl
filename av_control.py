#!/usr/bin/env python

"""
Manage I/O between a collection of A/V devices.

The A/V devices (and some not-so-A/V devices) are each represented by a class
instance derived from the AV_Device API.

The A/V devices are controlled by an AV_Loop instance, which mediates
communication and runtime between the instantiated devices.

Devices may submit commands (strings) to the AV_Loop, which then dispatches the
command to the command handler registered for that command (or falls back to
the empty ('') catch-all command handler if no handler is registered for the
given command).

Additionally, AV_Devices may register I/O handlers with the AV_Loop, which will
then listen for I/O events on the given file descriptors.
"""

import sys
import os
import time
import select
import argparse
from tornado.ioloop import IOLoop

from hdmi_switch import HDMI_Switch
from avr_device import AVR_Device
from http_server import AV_HTTPServer
from av_loop import AV_Loop


Devices = (
	("hdmi", HDMI_Switch),
	("avr",  AVR_Device),
	("http", AV_HTTPServer),
)

AVR_Device.DefaultTTY = "/dev/ttyUSB1"


def main(args):
	parser = argparse.ArgumentParser(
		description = "Controller daemon for A/V devices")
	for name, cls in Devices:
		cls.register_args(name, parser)

	IOLoop.configure(AV_Loop, parsed_args = vars(parser.parse_args(args)))
	mainloop = IOLoop.instance()

	for name, cls in Devices:
		try:
			print("*** Initializing %s..." % (cls.Description), end=' ')
			mainloop.add_device(name, cls(mainloop, name))
			print("done")
		except Exception as e:
			print(e)

	if not mainloop.cmd_handlers:
		print("No A/V commands registered. Aborting...")
		return 1

	def cmd_catch_all(empty, cmd):
		"""Handle commands that are not handled elsewhere."""
		assert empty == ""
		print("*** Unknown A/V command: '%s'" % (cmd))
	mainloop.add_cmd_handler("", cmd_catch_all)

	print("Starting A/V controller main loop.")
	return mainloop.run()


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
