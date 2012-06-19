#!/usr/bin/env python2

"""
Receive commands for controlling the HDMI switch and AVR on a FIFO.

Forward commands to the HDMI switch which is connected to a serial port.

Receive status updates from AVR connected on a serial port.
Forward commands to AVR over the serial port.

Keep as little local state as possible
"""

import os
import time
import atexit

from hdmi_switch import HDMI_Switch
from avr_conn import AVR_Connection
from avr_status import AVR_Status
from avr_command import AVR_Command

# Connection point to clients that want to control the AVR
fifo_name = "/tmp/avr_control"

# Where the HDMI switch is connected
HDMI_tty = "/dev/ttyUSB0"

# Where the AVR itself is connected
AVR_tty = "/dev/ttyUSB1"

# Map FIFO command to corresponding HDMI command
HDMI_Map = {
	"hdmi0": "off",
	"hdmi1": "1",
	"hdmi2": "2",
	"hdmi3": "3",
	"hdmi4": "4",
}

# Map FIFO command to corresponding AVR command
AVR_Map = {
	"on":   "POWER ON",
	"off":  "POWER OFF",
	"mute": "MUTE",
	"vol+": "VOL UP",
	"vol-": "VOL DOWN",
}

def destroy_fifo():
	try:
		os.remove(fifo_name)
	except:
		pass


def create_fifo():
	# Open FIFO for reading commands from clients
	if os.path.exists(fifo_name):
		raise OSError("%s exists. Another instance of %s running?" % (
			fifo_name, os.path.basename(sys.argv[0])))
	os.mkfifo(fifo_name)
	atexit.register(destroy_fifo)
	return os.open(fifo_name, os.O_RDONLY | os.O_NONBLOCK)


def usage(msg):
	print msg + ":"
	print "Usage:"
	print "  avr_control.py [--hdmi <serial_port>] [--avr <serial_port>]"
	print
	print "  Then write any of the following commands to %s:" % (fifo_name)
	for cmd in sorted(AVR_Map.keys()):
		print "    %s" % (cmd)
	return 1


def main(args, HDMI_tty = HDMI_tty, AVR_tty = AVR_tty):
	if len(args) >= 2 and args[0] == "--hdmi":
		HDMI_tty = args[1]
		args = args[2:]
	if len(args) >= 2 and args[0] == "--avr":
		AVR_tty = args[1]
		args = args[2:]

	if args:
		return usage("Unknown arg(s): '%s'" % (" ".join(args)))

	fifo_fd = create_fifo()
	hdmi = HDMI_Switch(HDMI_tty)
	avr = AVR_Connection(AVR_tty)

	prev_dgram = None
	fifo_input = ""
	ts = time.time()
	while True:
		fifo_input += os.read(fifo_fd, 64)
		cmds = fifo_input.split("\n")
		fifo_input = cmds.pop()
		for cmd in cmds:
			if cmd in HDMI_Map:
				hdmi.send_command(HDMI_Map[cmd])
			elif cmd in AVR_Map:
				avr.send_dgram(AVR_Command(AVR_Map[cmd]).dgram())
			else:
				print "Unknown command '%s'" % (cmd)
		dgram = avr.write_and_recv()
		if dgram == prev_dgram:
			continue # Skip if unchanged
		prev_dgram = dgram

		status = AVR_Status.from_dgram(dgram)

		now = time.time()
		print "%s (period: %f seconds)" % (status, now - ts)
		ts = now

	avr.close()
	os.close(fifo_fd)
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
