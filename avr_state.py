#!/usr/bin/env python2


class AVR_State(object):
	"""Encapsulate the current state of the Harman/Kardon AVR 430."""

	def __init__(self, name, av_loop):
		self.name = name
		self.submit_cmd = av_loop.submit_cmd
		self.get_ts = av_loop.get_ts

		self.last_ts = 0
		self.last_status = None

	def __str__(self):
		if self.last_status is None:
			return "UNKNOWN"
		s = self.last_status
		return "%s|%s|%s/%s/%s -> %s" % (
			s.line1, s.line2, s.source(), s.ch_string(),
			s.short_surr_string(), s.short_spkr_string())

	def json(self):
		"""Dump the current state as JSON."""
		import json
		if self.last_status is None:
			return json.dumps(None)

		return json.dumps({
			"line1":       self.last_status.line1,
			"line2":       self.last_status.line2,
			"standby":     self.last_status.standby(),
			"mute":        self.last_status.mute(),
			"volume":      self.last_status.volume(),
			"surround":    list(self.last_status.surround()),
			"surr_string": self.last_status.surr_string(),
			"surr_str":    self.last_status.short_surr_string(),
			"channels":    list(self.last_status.channels()),
			"ch_string":   self.last_status.ch_string(),
			"speakers":    list(self.last_status.speakers()),
			"spkr_string": self.last_status.spkr_string(),
			"spkr_str":    self.last_status.short_spkr_string(),
			"source":      self.last_status.source(),
		})

	def update(self, status):
		ts = self.get_ts()

		if self.off(ts) and status.standby():
			# We just received power. Trigger wake from standby.
			self.submit_cmd("%s on" % (self.name))

		ret = status != self.last_status
		self.last_ts = ts
		self.last_status = status

		if ret:
			self.submit_cmd("%s update" % (self.name))

		return ret

	def off(self, ts = None):
		"""Return True iff the AVR is disconnected, or turned off."""
		if ts is None:
			ts = self.get_ts()

		# Assume that the AVR is off if we haven't heard from it in 0.5s
		return ts > self.last_ts + 0.5
