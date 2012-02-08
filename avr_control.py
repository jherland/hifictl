#!/usr/bin/env python2

import os
import time
import atexit
import serial

from avr_conn import AVR_Connection
from avr_status import AVR_Status
from avr_command import AVR_Command
from avr_state import AVR_State


fifo_name = "/tmp/avr_control"


def create_fifo():
	# Open FIFO for reading commands from clients
	if os.path.exists(fifo_name):
		raise OSError("%s exists. Another instance of %s running?" % (
			fifo_name, os.path.basename(sys.argv[0])))
	os.mkfifo(fifo_name)
	return os.open(fifo_name, os.O_RDONLY | os.O_NONBLOCK)


@atexit.register
def destroy_fifo():
	try:
		os.remove(fifo_name)
	except:
		pass


def usage(msg):
	print msg + ":"
	print "Usage:"
	print "  avr_control.py <cmd>"
	print "  (where <cmd> is one of %s)" % (sorted(AVR_Commands.keys()))


def main(args):
	if len(args) >= 2 and args[0] == "-D":
		tty = args[1]
		args = args[2:]
	else:
		tty = "/dev/ttyUSB1"

	f = serial.Serial(tty, 38400)

	# It seems pyserial needs the rtscts flag toggled in
	# order to communicate consistently with the remote end.
	f.rtscts = True
	f.rtscts = False


	fifo_fd = create_fifo()
	conn = AVR_Connection(f)
	state = AVR_State(conn)

	# Interpret command-line args as a single command to be sent to the AVR.
	if args:
		conn.send_dgram(AVR_Command(" ".join(args)).dgram())

	prev_dgram = None
	fifo_input = ""
	ts = time.time()
	while True:
		fifo_input += os.read(fifo_fd, 64)
		cmds = fifo_input.split("\n")
		fifo_input = cmds.pop()
		for cmd in cmds:
			state.handle_client_command(cmd.strip())
		dgram = conn.write_and_recv()
		if dgram == prev_dgram:
			continue # Skip if unchanged
		prev_dgram = dgram

		status = AVR_Status.from_dgram(dgram)
		state.update(status)

		now = time.time()
		print "%s -> %s (period: %f seconds)" % (status, state, now - ts)
		ts = now

	conn.close()
	os.close(fifo_fd)
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
