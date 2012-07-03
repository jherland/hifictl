#!/usr/bin/env python2


class AV_Device(object):
	"""Encapsulate an A/V device that can be controlled from AV_Loop."""

	Description = "Unspecified A/V device"

	Debug = False

	@classmethod
	def register_args(cls, arg_parser):
		"""Must be overridden if you want to add cmdline params."""
		pass

	def debug(self, s):
		"""Convenience method for debug output."""
		if self.Debug:
			import time
			ts = time.time() - self.av_loop.t0
			print "%7.2f: %s" % (ts, self), s

	def __init__(self, av_loop, name):
		self.av_loop = av_loop
		self.name = name

	def __str__(self):
		return "<%s %s>" % (self.__class__.__name__, self.name)
