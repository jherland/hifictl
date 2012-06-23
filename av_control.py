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

	epoll = select.epoll()
	t_start = time.time()

	devices = {} # Map device namespaces to AV_Device objects.
	device_fds = {} # Map device fds to AV_Device objects.

	def cmd_dispatcher(cmd):
		"""Dispatch commands to their appropriate device handlers.

		Parse command strings of the form "$namespace $subcmd...",
		and pass "$subcmd..." on to the device named $namespace.
		"""
		ts = time.time() - t_start
		print "cmd_dispatcher(%s)" % (cmd)
		namespace, subcmd = cmd.split(" ", 1)
		if namespace in devices:
			devices[namespace].handle_cmd(subcmd, ts)
		else:
			print "Unknown namespace '%s'" % (namespace)

	for dev in Devices:
		try:
			namespace = dev['name']
			cls = dev['class']
			print "*** Initializing %s..." % (cls.Description),
			dev = cls(namespace, parsed_args[namespace])
			dev_fd = dev.register(epoll, cmd_dispatcher)
			devices[namespace] = dev
			device_fds[dev_fd] = dev
			print "done"
		except Exception as e:
			print e

	if not devices:
		print "No devices found. Aborting..."
		return 1

	print "Starting A/V controller main loop"
	try:
		while True:
			for fd, events in epoll.poll():
				ts = time.time() - t_start
				assert fd in device_fds
				device_fds[fd].handle_events(epoll, events, ts)
	except KeyboardInterrupt:
		print "Aborted by user"

	epoll.close()
	return 0


if __name__ == '__main__':
	sys.exit(main(sys.argv[1:]))
