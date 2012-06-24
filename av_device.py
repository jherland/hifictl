#!/usr/bin/env python2


class AV_Device(object):
	"""Encapsulate an A/V device that can be controlled from av_control.

	The device must be hooked up to some file descriptor that can be passed
	to epoll. It must also declare a namespace which is used to select which
	commands to pass to its handle_cmd() method.

	Finally, this class declares methods for handling incoming epoll events
	and A/V commands."""

	Description = "Unspecified A/V device"

	Debug = False

	def debug(self, ts, s):
		"""Convenience method for debug output."""
		if self.Debug:
			print "%.2f: %s" % (ts, self), s

	def __init__(self, cmd_namespace):
		self.cmd_namespace = cmd_namespace
		self.cmd_dispatcher = None

	def __str__(self):
		return "<%s %s>" % (self.__class__.__name__, self.cmd_namespace)

	def register(self, epoll, cmd_dispatcher):
		"""Register this device's file desc. and event mask with epoll.

		Also, return this device's file descriptor, so that the
		surrounding epoll loop can map events back to this object.

		Finally, use the given command dispatcher to dispatch A/V
		commands to the surrounding system.
		"""
		raise NotImplementedError

	def handle_events(self, epoll, events, ts = 0):
		"""Handle the given events code from the given epoll object.

		The given code is a bitwise combination of the events returned
		from self.eventmask().

		This method is free to call epoll.modify()
		"""
		raise NotImplementedError

	def handle_cmd(self, cmd, ts = 0):
		"""Handle the given A/V control command.

		Only A/V control commands of the form "$namespace $cmd..." where
		$namespace equals self.cmd_namespace are passed to this method,
		and only the "$cmd..." part of the command is passed.
		"""
		raise NotImplementedError
