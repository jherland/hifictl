#!/usr/bin/env python2

import pty
import os
import fcntl
import termios
import time

from timed_queue import TimedQueue
from avr_dgram import AVR_Datagram
from avr_status import AVR_Status
from avr_command import AVR_Command


class Fake_SerialDevice(object):
	"""Create a local serial-port-like device that can be used to
	impersonate real devices connected to a serial port.

	This is useful for testing programs communicating with a serial
	device when the serial device is not available.
	"""

	def __init__(self):
		self.master, self.slave = pty.openpty()
		self._client_name = os.ttyname(self.slave)

		# Close the slave descriptor. It will be reopened by the client
		os.close(self.slave)

		# Make the master descriptor non-blocking.
		fl = fcntl.fcntl(self.master, fcntl.F_GETFL)
		fcntl.fcntl(self.master, fcntl.F_SETFL, fl | os.O_NONBLOCK)

		# Backup old term settings and setup new settings
		self.term = termios.tcgetattr(self.master)
		newterm = termios.tcgetattr(self.master)
		newterm[3] = newterm[3] & ~termios.ECHO # lflags
		termios.tcsetattr(self.master, termios.TCSAFLUSH, newterm)

	def __del__(self):
		# Close the remaining descriptor
		termios.tcsetattr(self.master, termios.TCSAFLUSH, self.term)
		os.close(self.master)

	def fileno(self):
		return self.master

	def client_name(self):
		return self._client_name


class Fake_AVR(object):
	"""Impersonate an AVR unit.

	Receive remote commands, update internal state and provide plausible
	AVR_Status messages.
	"""

	EmptyIcons = chr(0x00) * 14
	DefaultIcons = "".join(map(chr, [0xc0, 0x00, 0x00, 0x00,
		0xfd, 0xfb, 0x7a, 0x00, 0xc0] + [0x00] * 5))

	StatusMap = {
		"standby": ("              ", "              ", EmptyIcons),
		"default": ("FAKE AVR      ", "DOLBY DIGITAL ", DefaultIcons),
		"mute":    ("     MUTE     ", "              ", DefaultIcons),
		"volume":  ("FAKE AVR      ", "  VOL %(volume)3i dB  ", DefaultIcons),
	}

	def __init__(self):
		self.t0 = time.time()

		self.standby = True
		self.mute    = False
		self.volume  = -35 # dB

		self.status_queue = TimedQueue(self.gen_status("standby"))

	def status(self):
		"""Return AVR_Status diagram for current state."""
		return self.status_queue.current()

	def gen_status(self, key):
		line1, line2, icons = self.StatusMap[key]
		d = self.__dict__
		return AVR_Status(line1 % d, line2 % d, icons)

	def handle_command(self, cmd):
		now = time.time()
		print "%7.2f: %10s" % (now - self.t0, cmd.keyword),
		if self.standby:
			if cmd.keyword == "POWER ON":
				self.standby = False
				self.status_queue.flush(self.gen_status("default"))
		else:
			if cmd.keyword == "POWER OFF":
				self.standby = True
				self.status_queue.flush(self.gen_status("standby"))
			elif cmd.keyword == "MUTE":
				self.mute = not self.mute
				self.status_queue.flush(self.gen_status(self.mute and "mute" or "default"))
			elif cmd.keyword == "VOL DOWN" or cmd.keyword == "VOL UP":
				self.volume += cmd.keyword == "VOL DOWN" and -1 or +1
				self.status_queue.flush(self.gen_status("default"))
				self.status_queue.add_relative(3, self.gen_status("volume"))
		print "->", self.status()


def main(args):
	tty = Fake_SerialDevice()
	print "You can now start ./av_control.py --avr %s" % (tty.client_name())

	# Repeatedly send status info every 5/100 seconds, until user aborts
	avr = Fake_AVR()
	recv_data = "" # Receive buffer
	recv_dgram_spec = ("PCSEND", 2, 4) # Receive PC->AVR remote commands
	send_dgram_spec = ("MPSEND", 3, 48) # Send AVR->PC status updates
	recv_dgram_len = AVR_Datagram.full_dgram_len(recv_dgram_spec)
	try:
		while True:
			try:
				recv_data += os.read(tty.fileno(), 1024)
			except OSError as e:
				if e.errno not in (5, 11): # EIO or EAGAIN
					raise e
			while len(recv_data) >= recv_dgram_len:
				dgram = recv_data[:recv_dgram_len]
				recv_data = recv_data[recv_dgram_len:]
				avr.handle_command(AVR_Command.from_dgram(
					AVR_Datagram.parse_dgram(
						dgram, recv_dgram_spec)))

			time.sleep(0.05)
			os.write(tty.fileno(), AVR_Datagram.build_dgram(
				avr.status().dgram(), send_dgram_spec))
	except KeyboardInterrupt:
		pass

	del tty
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
