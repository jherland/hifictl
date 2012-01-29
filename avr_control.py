#!/usr/bin/env python2

import time

from avr_conn import AVR_Connection
from avr_status import AVR_Status
from avr_command import AVR_Command


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
	conn = AVR_Connection(tty)

	# Interpret command-line args as a single command to be sent to the AVR.
	if args:
		conn.send_dgram(AVR_Command(" ".join(args)).dgram())

	prev_dgram = None
	ts = time.time()
	while True:
		dgram = conn.write_and_recv()
		if dgram == prev_dgram:
			continue # Skip if unchanged
		prev_dgram = dgram

		status = AVR_Status.from_dgram(dgram)

		now = time.time()
		print "%s (period: %f seconds)" % (status, now - ts)
		ts = now

	conn.close()
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
