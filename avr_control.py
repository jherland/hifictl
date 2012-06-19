#!/usr/bin/env python2

"""
Receive commands for controlling the AVR on a FIFO.

Receive status updates from AVR connected on a serial port.
Forward commands to AVR over the serial port.

Keep as little local state as possible
"""

import os
import time
import atexit

from avr_conn import AVR_Connection
from avr_status import AVR_Status
from avr_command import AVR_Command

# Connection point to clients that want to control the AVR
fifo_name = "/tmp/avr_control"

# Where the AVR itself is connected
avr_tty = "/dev/ttyUSB1"

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
	print "  avr_control.py [-D <serial_port>]"
	print
	print "  Then write any of the following commands to %s:" % (fifo_name)
	for cmd in sorted(AVR_Map.keys()):
		print "    %s" % (cmd)
	return 1


def main(args):
	if len(args) >= 2 and args[0] == "-D":
		avr_tty = args[1]
		args = args[2:]

	if args:
		return usage("Unknown arg(s): '%s'" % (" ".join(args)))

	fifo_fd = create_fifo()
	conn = AVR_Connection(avr_tty)

	prev_dgram = None
	fifo_input = ""
	ts = time.time()
	while True:
		fifo_input += os.read(fifo_fd, 64)
		cmds = fifo_input.split("\n")
		fifo_input = cmds.pop()
		for cmd in cmds:
			if cmd not in AVR_Map:
				print "Unknown command '%s'" % (cmd)
			else:
				conn.send_dgram(AVR_Command(AVR_Map[cmd]).dgram())
		dgram = conn.write_and_recv()
		if dgram == prev_dgram:
			continue # Skip if unchanged
		prev_dgram = dgram

		status = AVR_Status.from_dgram(dgram)

		now = time.time()
		print "%s (period: %f seconds)" % (status, now - ts)
		ts = now

	conn.close()
	os.close(fifo_fd)
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
