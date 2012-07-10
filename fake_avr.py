#!/usr/bin/env python2

import pty
import os
import fcntl
import termios
import time
from tornado.ioloop import PeriodicCallback

from av_device import AV_Device
from timed_queue import TimedQueue
from avr_dgram import AVR_Datagram
from avr_status import AVR_Status
from avr_command import AVR_Command


class Fake_SerialDevice(AV_Device):
	"""Create a local serial-port-like device that can be used to
	impersonate real devices connected to a serial port.

	This is useful for testing programs communicating with a serial
	device when the serial device is not available.
	"""

	Description = "Fake serial port device"

	def __init__(self, av_loop, name):
		AV_Device.__init__(self, av_loop, name)

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

		self.av_loop.add_handler(self.master, self.handle_io,
			self.av_loop.READ)

	def __del__(self):
		# Close the remaining descriptor
		termios.tcsetattr(self.master, termios.TCSAFLUSH, self.term)
		os.close(self.master)

	def fileno(self):
		return self.master

	def client_name(self):
		return self._client_name

	def handle_io(self, fd, events):
		assert fd == self.master
#		self.debug("handle_io(%i, %i)" % (fd, events))

		if events & self.av_loop.READ:
#			try:
				self.handle_read()
#			except Exception as e:
#				self.debug("handle_read(): %s" % (e))
		if events & self.av_loop.WRITE:
#			try:
				self.handle_write()
#			except Exception as e:
#				self.debug("handle_write(): %s" % (e))
		if events & self.av_loop.ERROR:
			# Ignore HUP and EIO, etc. FIXME: Is this safe?
			pass

		events &= ~(self.av_loop.READ | self.av_loop.WRITE | self.av_loop.ERROR)
		if events:
			self.debug("Unhandled events: %u" % (events))


	def handle_read(self):
		"""Attempt to read data from the PTY.

		This method should probably be overridden in subclasses.
		"""
		print os.read(self.master, 64 * 1024)

	def handle_write(self):
		"""Must be overridden in subclasses that poll for writes."""
		raise NotImplementedError


class Fake_AVR(Fake_SerialDevice):
	"""Impersonate an AVR unit.

	Receive remote commands, update internal state and provide plausible
	AVR_Status messages.
	"""

	Description = "Fake Harman/Kardon AVR 430"

	EmptyIcons = chr(0x00) * 14
	DefaultIcons = "".join(map(chr, [0xc0, 0x00, 0x00, 0x00,
		0xfd, 0xfb, 0x7a, 0x00, 0xc0] + [0x00] * 5))

	StatusMap = {
		"standby": ("              ", "              ", EmptyIcons),
		"default": ("FAKE AVR      ", "DOLBY DIGITAL ", DefaultIcons),
		"mute":    ("     MUTE     ", "              ", DefaultIcons),
		"volume":  ("FAKE AVR      ", "  VOL %(volume)3i dB  ", DefaultIcons),
	}

	RecvDGramSpec = ("PCSEND", 2, 4) # Receive PC->AVR remote commands
	SendDGramSpec = ("MPSEND", 3, 48) # Send AVR->PC status updates

	def __init__(self, av_loop, name):
		Fake_SerialDevice.__init__(self, av_loop, name)

		self.standby = True
		self.mute    = False
		self.volume  = -35 # dB

		self.status_queue = TimedQueue(self.gen_status("standby"))

		self.write_timer = PeriodicCallback(self.write_now, 50, av_loop)
		self.write_timer.start()

		self.recv_dgram_len = AVR_Datagram.full_dgram_len(self.RecvDGramSpec)
		self.recv_data = "" # Receive buffer

		self.t0 = time.time()

	def __del__(self):
		self.write_timer.stop()

	def write_now(self):
		os.write(self.master, AVR_Datagram.build_dgram(
			self.status().dgram(), self.SendDGramSpec))

	def status(self):
		"""Return AVR_Status diagram for current state."""
		return self.status_queue.current()

	def handle_read(self):
		self.recv_data += os.read(self.master, 1024)
		while len(self.recv_data) >= self.recv_dgram_len:
			dgram = self.recv_data[:self.recv_dgram_len]
			self.recv_data = self.recv_data[self.recv_dgram_len:]
			self.handle_command(AVR_Command.from_dgram(
				AVR_Datagram.parse_dgram(dgram,
					self.RecvDGramSpec)))

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
	import argparse

	from av_loop import AV_Loop

	parser = argparse.ArgumentParser(
		description = Fake_AVR.Description)
	Fake_AVR.register_args("avr", parser)

	mainloop = AV_Loop(vars(parser.parse_args(args)))
	avr = Fake_AVR(mainloop, "avr")

	print "You can now start ./av_control.py --avr-tty %s" % (
		avr.client_name())

	return mainloop.run()


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
