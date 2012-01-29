#!/usr/bin/env python2

from avr_conn import AVR_Connection
from avr_command import AVR_Command


class AVR_State(object):
	"""Encapsulate and control the full state of the AVR."""

	# Volume limits
	MinVol = -80 # dB
	MaxVol = -20 # +8 dB

	@staticmethod
	def vol_string(vol):
		if vol is None:
			return "<unknown>"
		else:
			return "%+ddB" % (vol)

	def __init__(self, conn):
		self.conn = conn # AVR_Connection object

		self.standby = None # Standby mode (unknown)
		self.cur_vol = None # Current volume (unknown)
		self.trg_vol = None # Target volume (no target)

	def __str__(self):
		if self.standby:
			return "<AVR_State: OFF>"

		return "<AVR_State: %s/%s>" % (
			self.vol_string(self.cur_vol),
			self.vol_string(self.trg_vol))

	def send_avr_command(self, avr_command):
		"""Send the given AVR command."""
		return self.conn.send_dgram(AVR_Command(avr_command).dgram())

	def update(self, status):
		"""Assimilate the given status update from the AVR.

		Adjust internal state according to the information in the given
		AVR_Status object.
		"""
		# Power on/off
		self.standby = status.standby()

		# Volume
		vol = status.volume()
		if vol is not None:
			self.cur_vol = vol
		if self.trg_vol is None:
			self.trg_vol = self.cur_vol

	def handle_client_command(self, cmd):
		"""Handle the given client command."""
		print "Handling command '%s'" % (cmd)
		args = cmd.lower().split()
		if args[0] == "standby":
			assert len(args) == 2
			assert args[1] in ("on", "true", "1", "off", "false", "0")
			self.set_standby(args[1] in ("on", "true", "1"))
		elif args[0] == "volume":
			assert len(args) == 3
			assert args[1] in ("set", "change")
			vol = int(args[2])
			if args[1] == "set":
				self.set_vol(vol)
			else:
				self.change_vol(vol)
		else:
			print "Unknown command '%s'" % (cmd)
		# Improve this by decorating "command" methods with "@command"
		# and auto-deriving this parser from the decorated methods

	def set_standby(self, standby = False):
		"""Disable/enable standby mode."""
		if standby != self.standby:
			if standby:
				self.send_avr_command("POWER OFF")
			else:
				self.send_avr_command("POWER ON")

	def set_vol(self, vol):
		"""Set the volume to the given absolute value.

		The given volume must be between MinVol and MaxVol.
		"""
		assert self.MinVol <= vol <= self.MaxVol
		self.trg_vol = vol

	def change_vol(self, vol):
		"""Adjust the volume by the given relative value."""
		self.trg_volume += vol
		if self.trg_volume > self.MaxVol:
			self.trg_volume = self.MaxVol
		if self.trg_volume < self.MaxVol:
			self.trg_volume = self.MinVol
