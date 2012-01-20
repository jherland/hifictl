#!/usr/bin/env python2

import pty
import os
import fcntl
import time
import avr_control

master, slave = pty.openpty()
print "You can now connect avr_control.py to %s" % (os.ttyname(slave))

# Close the slave descriptor. It will be reopened by the client (avr_control.py)
os.close(slave)

# Make the master descriptor non-blocking.
fl = fcntl.fcntl(master, fcntl.F_GETFL)
fcntl.fcntl(master, fcntl.F_SETFL, fl | os.O_NONBLOCK)

# Prepare the status info to send to the client
status = avr_control.AVR_Status(
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
os.close(master)