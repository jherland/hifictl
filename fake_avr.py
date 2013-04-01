#!/usr/bin/env python

import os
import time
from tornado.ioloop import PeriodicCallback

from fake_serial_device import Fake_SerialDevice
from timed_queue import TimedQueue
from avr_dgram import AVR_Datagram
from avr_status import AVR_Status
from avr_command import AVR_Command


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
		print("%7.2f: %10s" % (now - self.t0, cmd.keyword), end=' ')
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
		print("->", self.status())


def main(args):
	import argparse

	from av_loop import AV_Loop

	parser = argparse.ArgumentParser(
		description = Fake_AVR.Description)
	Fake_AVR.register_args("avr", parser)

	mainloop = AV_Loop(vars(parser.parse_args(args)))
	avr = Fake_AVR(mainloop, "avr")

	print("You can now start ./av_control.py --avr-tty %s" % (
		avr.client_name()))

	return mainloop.run()


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
