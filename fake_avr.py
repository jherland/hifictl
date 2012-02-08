#!/usr/bin/env python2

import pty
import os
import fcntl
import termios
import time

from avr_conn import AVR_Connection
from avr_status import AVR_Status
from avr_command import AVR_Command


def main(args):
	master, slave = pty.openpty()
	print "You can now connect avr_control.py to %s" % (os.ttyname(slave))

	# Close the slave descriptor. It will be reopened by the client
	os.close(slave)

	# Make the master descriptor non-blocking.
	fl = fcntl.fcntl(master, fcntl.F_GETFL)
	fcntl.fcntl(master, fcntl.F_SETFL, fl | os.O_NONBLOCK)

	# Backup old term settings and setup new settings
	oldterm = termios.tcgetattr(master)
	newterm = termios.tcgetattr(master)
	newterm[3] = newterm[3] & ~termios.ECHO # lflags
	termios.tcsetattr(master, termios.TCSAFLUSH, newterm)

	# Prepare the status info to send to the client
	status = AVR_Status(
		'HTPC          ',
		'DOLBY DIGITAL ',
		"".join(map(chr, [0xc0, 0x00, 0x00, 0x00, 0xfd, 0xfb, 0x7a,
				  0x00, 0xc0, 0x00, 0x00, 0x00, 0x00, 0x00])))

	# Repeatedly send status info every 5/100 seconds, until user aborts
	start = time.time()
	now = start
	input_data = ""
	out_dgram_spec = ("MPSEND", 3, 48) # Send AVR->PC status updates
	in_dgram_spec = ("PCSEND", 2, 4) # Receive PC->AVR remote commands
	in_dgram_len = AVR_Connection.full_dgram_len(in_dgram_spec)
	try:
		while True:
			try:
				input_data += os.read(master, 1024)
			except OSError as e:
				if e.errno not in [5, 11]:
					raise e
			while len(input_data) >= in_dgram_len:
				dgram = input_data[:in_dgram_len]
				input_data = input_data[in_dgram_len:]
				cmd_data = AVR_Connection.parse_dgram(dgram, in_dgram_spec)
				cmd = AVR_Command.from_dgram(cmd_data)
				print "(%fs) Received %s" % (now - start, cmd)
			time.sleep(0.05)
			now = time.time()
			if int((now - start) / 0.5) % 2:
				status.line1 = 'HTPC2         '
			else:
				status.line1 = 'HTPC          '
			os.write(master, AVR_Connection.build_dgram(
				status.dgram(), out_dgram_spec))
	except KeyboardInterrupt:
		pass

	# Close the remaining descriptor
	termios.tcsetattr(master, termios.TCSAFLUSH, oldterm)
	os.close(master)
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
