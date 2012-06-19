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
import serial

from avr_conn import AVR_Connection
from avr_status import AVR_Status
from avr_command import AVR_Command

fifo_name = "/tmp/avr_control"

avr_tty = "/dev/ttyUSB1"
avr_baudrate = 38400

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
	print "  avr_control.py"
	print "  (then write <cmd> to %s, where <cmd> is one of %s)" % (
		fifo_name, sorted(AVR_Commands.keys()))


def main(args):
	if len(args) >= 2 and args[0] == "-D":
		avr_tty = args[1]
		args = args[2:]

	if args:
		usage("Unknown arg(s): '%s'" % (" ".join(args)))

	# It seems pyserial needs the rtscts flag toggled in
	# order to communicate consistently with the remote end.
	f = serial.Serial(avr_tty, avr_baudrate, rtscts = True)
	f.rtscts = False

	fifo_fd = create_fifo()
	conn = AVR_Connection(f)

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
