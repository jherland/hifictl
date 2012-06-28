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
	{
		'name':         "hdmi",
		'class':        HDMI_Switch,
		'default_path': "/dev/ttyUSB0",
		'path_help':    "Path to tty connected to HDMI switch",
	},
	{
		'name':         "avr",
		'class':        AVR_Device,
		'default_path': "/dev/ttyUSB1",
		'path_help':    "Path to tty connected to AVR",
	},
	{
		'name':         "fifo",
		'class':        AV_FIFO,
		'default_path': "/tmp/av_control",
		'path_help':    "Path to A/V command FIFO",
	},
	{
		'name':         "http",
		'class':        AV_HTTPServer,
		'default_path': "./http",
		'path_help':    "Path to static HTTP resources",
	},
)


def main(args):
	parser = argparse.ArgumentParser(
		description = "Controller daemon for A/V devices")

	for dev in Devices:
		parser.add_argument("--%s" % (dev['name']),
			default = dev['default_path'],
			help = "%s (default: %%(default)s)" % (dev['path_help']),
			metavar = "PATH")

	parsed_args = vars(parser.parse_args(args))

	mainloop = AV_Loop()

	devices = {} # Map device names to AV_Device objects.

	def cmd_catch_all(namespace, cmd):
		"""Handle commands that are not handled elsewhere."""
		print "*** Unknown A/V command: '%s %s'" % (namespace, cmd)
	mainloop.add_cmd_handler('', cmd_catch_all)

	for dev in Devices:
		try:
			name = dev['name']
			cls = dev['class']
			print "*** Initializing %s..." % (cls.Description),
			dev = cls(mainloop, name, parsed_args[name])
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
