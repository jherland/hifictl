#!/usr/bin/env python2


class AVR_State(object):
	"""Encapsulate the current state of the Harman/Kardon AVR 430."""

	def __init__(self, name, submit_cmd):
		self.name = name
		self.submit_cmd = submit_cmd

		self.last_ts = 0
		self.last_status = None

	def __str__(self):
		if self.last_status is None:
			return "UNKNOWN"
		s = self.last_status
		return "%s\n%s\n%s/%s/%s -> %s" % (
			s.line1, s.line2, s.source(), s.ch_string(),
			s.short_surr_string(), s.short_spkr_string())

	def update(self, ts, status):
		if self.off(ts) and status.standby():
			# We just received power. Trigger wake from standby.
			self.submit_cmd("%s on" % (self.name))

		ret = status != self.last_status
		self.last_ts = ts
		self.last_status = status
		return ret

	def off(self, ts):
		"""Return True iff the AVR is disconnected, or turned off."""
		# Assume that the AVR is off if we haven't heard from it in 0.5s
		return ts > self.last_ts + 0.5
