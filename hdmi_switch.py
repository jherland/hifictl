#!/usr/bin/env python2

import serial


class HDMI_Switch(object):
	"""Simple wrapper for sending commands to a HDMI switch.

	Encapsulate RS-232 commands being sent to a Marmitek Connect411 HDMI
	switch connected to a serial port.
	"""

	LF = "\n\r"

	Commands = {
		"1":       LF + "1" + LF,
		"2":       LF + "2" + LF,
		"3":       LF + "3" + LF,
		"4":       LF + "4" + LF,
		"on":      LF + "5" + LF,
		"off":     LF + "5" + LF,
		"version": LF + "v" + LF,
		"help":    LF + "?" + LF,
	}

	def __init__(self, serial_port = "/dev/ttyUSB0", baudrate = 19200):
		# It seems pyserial needs the rtscts flag toggled in order to
		# communicate consistently with the remote end.
		self.ser = serial.Serial(serial_port, baudrate, rtscts = True)
		self.ser.rtscts = False
		self.ser.timeout = 0.2 # Read timeout

	def send_command(self, cmd):
		assert cmd in self.Commands
		written = self.ser.write(self.Commands[cmd])
		assert written == len(self.Commands[cmd])
		return self.ser.read(1024)

	def on(self):
		return self._send_command("on")

	def off(self):
		return self._send_command("off")

	def switch(self, port):
		assert port in ("1", "2", "3", "4")
		return self._send_command(port)

	def version(self):
		return self._send_command("version")

	def help(self):
		return self._send_command("help")


def main(args):
	if not args:
		args = ["version"]

	hs = HDMI_Switch()
	for arg in args:
		print "Sending command '%s' to HDMI switch" % (arg)
		print hs.send_command(arg)

	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
