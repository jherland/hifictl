#!/usr/bin/env python2

import serial
import time

serial_device = "/dev/ttyUSB0"
serial_baudrate = 19200

lf = "\n\r"

commands = {
	"1":   lf + "1" + lf,
	"2":   lf + "2" + lf,
	"3":   lf + "3" + lf,
	"4":   lf + "4" + lf,
	"on":  lf + "5" + lf,
	"off": lf + "5" + lf,
#	"ver": lf + "v" + lf,
}

def usage(msg):
	print msg + ":"
	print "Usage:"
	print "  hdmi_switch.py <cmd>"
	print "  (where <cmd> is one of %s)" % (sorted(commands.keys()))

def main(args):
	if not len(args) == 1:
		return usage("Wrong number of args")
	cmd = args[0]
	if cmd not in commands:
		return usage("Unknown command '%s'" % (cmd))

	# It seems pyserial needs the rtscts flag toggled in order to
	# communicate consistently with the remote end.	
	ser = serial.Serial(serial_device, serial_baudrate, rtscts = True)
	ser.rtscts = False

	written = ser.write(commands[cmd])
	assert written == len(commands[cmd])

	ser.close()
	return 0

if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
