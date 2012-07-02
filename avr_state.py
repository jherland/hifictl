#!/usr/bin/env python2

from avr_status import AVR_Status


class AVR_State(object):
	"""Encapsulate the current state of the Harman/Kardon AVR 430."""

	def __init__(self, name, av_loop):
		self.name = name
		self.submit_cmd = av_loop.submit_cmd
		self.get_ts = av_loop.get_ts

		self.last_ts = 0
		self.last_status = None

		self.standby  = None  # bool
		self.mute     = None  # bool
		self.volume   = None  # int
		self.source   = None  # string
		self.surround = set() # set(strings)
		self.channels = set() # set(strings)
		self.speakers = set() # set(strings)
		self.line1    = None  # string
		self.line2    = None  # string

	def __str__(self):
		props = []
		if self.off():
			props.append("off")
		elif self.standby:
			props.append("standby")
		else:
			if self.mute:
				props.append("mute")
			if self.volume is not None:
				props.append("%idB" % (self.volume))
			props.append("%s/%s/%s/ -> %s" % (
				self.source,
				AVR_Status.channels_string(self.channels),
				AVR_Status.surround_string(self.surround),
				AVR_Status.speakers_string(self.speakers),
			))
			props.append("'%s'" % (self.line1))
			props.append("'%s'" % (self.line2))
		return "<AVR_State " + " ".join(props) + ">"

	def json(self):
		"""Dump the current state as JSON."""
		import json
		if self.last_status is None:
			return json.dumps(None)

		return json.dumps({
			"off":             self.off(),
			"standby":         self.standby,
			"mute":            self.mute,
			"volume":          self.volume,
			"surround":        list(self.surround),
			"surround_string": AVR_Status.surround_string(self.surround),
			"surround_str":    AVR_Status.surround_str(self.surround),
			"channels":        list(self.channels),
			"channels_string": AVR_Status.channels_string(self.channels),
			"speakers":        list(self.speakers),
			"speakers_string": AVR_Status.speakers_string(self.speakers),
			"speakers_str":    AVR_Status.speakers_str(self.speakers),
			"source":          self.source,
			"line1":           self.line1,
			"line2":           self.line2,
		})

	def update(self, status):
		# Record pre-update state, to compare to post-update state:
		pre_state = str(self)

		ts = self.get_ts()

		# Trigger wake from standby if we just went from OFF -> STANDBY
		if self.off(ts) and status.standby():
			self.submit_cmd("%s on" % (self.name))

		self.last_ts = ts
		self.last_status = status

		self.standby = status.standby()
		self.mute = status.mute()
		if status.volume() is not None:
			self.volume = status.volume()
		self.surround = status.surround()
		if status.channels():
			self.channels = status.channels()
		self.speakers = status.speakers()
		self.source = status.source()
		if not (status.mute() and not status.line1.strip()):
			self.line1 = status.line1
		self.line2 = status.line2

		# Figure out if we actually changed state
		post_state = str(self)
		if pre_state != post_state:
			self.submit_cmd("%s update" % (self.name))
			return True
		return False

	def off(self, ts = None):
		"""Return True iff the AVR is disconnected, or turned off."""
		if ts is None:
			ts = self.get_ts()

		# Assume the AVR is off if we haven't heard from it in 0.5s
		return ts > self.last_ts + 0.5
