#!/usr/bin/env python2

import time

from avr_status import AVR_Status


class AVR_State(object):
	"""Encapsulate the current state of the Harman/Kardon AVR 430."""

	def __init__(self, name, av_loop):
		self.name = name
		self.av_loop = av_loop

		self.watchdog = None  # Times out if we don't get status updates

		self.off      = None  # bool
		self.standby  = None  # bool
		self.mute     = None  # bool
		self.volume   = None  # int
		self.source   = None  # string
		self.surround = set() # set(strings)
		self.channels = set() # set(strings)
		self.speakers = set() # set(strings)
		self.line1    = None  # string
		self.line2    = None  # string

		self.refresh_watchdog()

	def __str__(self):
		props = []
		if self.off:
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
		return json.dumps({
			"off":             self.off,
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

	def trigger_watchdog(self):
		self.off = True
		self.watchdog = None
		self.av_loop.submit_cmd("%s update" % (self.name))

	def refresh_watchdog(self, timeout = 0.5):
		if self.watchdog:
			self.av_loop.remove_timeout(self.watchdog)
		self.watchdog = self.av_loop.add_timeout(time.time() + timeout,
			self.trigger_watchdog)

	def update(self, status):
		# Record pre-update state, to compare to post-update state:
		pre_state = str(self)

		# Trigger wake from standby if we just went from OFF -> STANDBY
		if self.off and status.standby():
			self.av_loop.submit_cmd("%s on" % (self.name))

		self.off = False
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

		self.refresh_watchdog()

		# Figure out if we actually changed state
		post_state = str(self)
		if pre_state != post_state:
			self.av_loop.submit_cmd("%s update" % (self.name))
			return True
		return False
