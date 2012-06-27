#!/usr/bin/env python2


class AVR_State(object):
	"""Encapsulate the current state of the Harman/Kardon AVR 430."""

	def __init__(self, namespace, cmd_dispatch):
		self.namespace = namespace
		self.cmd_dispatch = cmd_dispatch

		self.last_ts = 0
		self.last_status = None

	def update(self, ts, status):
		if self.off(ts) and status.standby():
			# We just received power. Trigger wake from standby.
			self.cmd_dispatch(self.namespace, "on")

		ret = status != self.last_status
		self.last_ts = ts
		self.last_status = status
		return ret

	def off(self, ts):
		"""Return True iff the AVR is disconnected, or turned off."""
		# Assume that the AVR is off if we haven't heard from it in 0.5s
		return ts > self.last_ts + 0.5
