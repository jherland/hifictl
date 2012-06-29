#!/usr/bin/env python2

"""
Receive commands for controlling the HDMI switch and AVR on a FIFO.

Forward commands to the HDMI switch which is connected to a serial port.

Receive status updates from AVR connected on a serial port.
Forward commands to AVR over the serial port.

Keep as little local state as possible
"""

import sys
import os
import time
import select
import argparse

from hdmi_switch import HDMI_Switch
from avr_device import AVR_Device
from av_fifo import AV_FIFO
from http_server import AV_HTTPServer
from av_loop import AV_Loop


Devices = (
	("hdmi", HDMI_Switch),
	("avr",  AVR_Device),
	("fifo", AV_FIFO),
	("http", AV_HTTPServer),
)

AVR_Device.DefaultTTY = "/dev/ttyUSB1"
AV_FIFO.DefaultFIFOPath = "/tmp/av_control"


def main(args):
	parser = argparse.ArgumentParser(
		description = "Controller daemon for A/V devices")
	for name, cls in Devices:
		cls.register_args(name, parser)

	mainloop = AV_Loop(vars(parser.parse_args(args)))
	devices = {} # Map device names to AV_Device objects.

	def cmd_catch_all(namespace, cmd):
		"""Handle commands that are not handled elsewhere."""
		print "*** Unknown A/V command: '%s %s'" % (namespace, cmd)
	mainloop.add_cmd_handler('', cmd_catch_all)

	for name, cls in Devices:
		try:
			print "*** Initializing %s..." % (cls.Description),
			dev = cls(mainloop, name)
			devices[name] = dev
			print "done"
		except Exception as e:
			print e

	if not devices:
		print "No A/V devices found. Aborting..."
		return 1

	print "Starting A/V controller main loop."
	return mainloop.run()


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
