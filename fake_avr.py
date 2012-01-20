#!/usr/bin/env python2

import pty
import os
import fcntl
import termios
import time

from avr_control import AVR_Command, AVR_Status

master, slave = pty.openpty()
print "You can now connect avr_control.py to %s" % (os.ttyname(slave))

# Close the slave descriptor. It will be reopened by the client (avr_control.py)
os.close(slave)

# Make the master descriptor non-blocking.
fl = fcntl.fcntl(master, fcntl.F_GETFL)
fcntl.fcntl(master, fcntl.F_SETFL, fl | os.O_NONBLOCK)

oldterm = termios.tcgetattr(master)
newterm = termios.tcgetattr(master)
newterm[3] = newterm[3] & ~termios.ECHO # lflags
termios.tcsetattr(master, termios.TCSAFLUSH, newterm)

# Prepare the status info to send to the client
status = AVR_Status(
	'HTPC          ',
	'DOLBY DIGITAL ',
	"".join(map(chr, [0xc0, 0x00, 0x00, 0x00, 0xfd, 0xfb, 0x7a, 0x00, 0xc0,
			  0x00, 0x00, 0x00, 0x00, 0x00])))

# Repeatedly send status info every 5/100 seconds, until aborted by the user
try:
	while True:
		time.sleep(0.05)
		os.write(master, status.dgram())
except KeyboardInterrupt:
	pass

# Close the remaining descriptor
termios.tcsetattr(master, termios.TCSAFLUSH, oldterm)
os.close(master)
