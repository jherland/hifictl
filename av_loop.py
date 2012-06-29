#!/usr/bin/env python2

import time
from tornado.ioloop import IOLoop

class AV_Loop(IOLoop):
	
	def __init__(self, parsed_args):
		IOLoop.__init__(self)
		self.install()

		self.args = parsed_args
		self.t0 = time.time() # Keep track of when we started

		self.cmd_handlers = {} # Map namespaces to command handlers

	def add_cmd_handler(self, namespace, handler):
		"""Registers the given handler to receive A/V commands within
		the given namespace.

		A/V commands are of the form "$namespace $subcmd...", where
		the $namespace part is matched against registered command
		handlers, and the appropriate handler is invoked with the
		$namespace as the first argument, and the $subcmd string as
		the second argument.
		"""
		if namespace in self.cmd_handlers:
			raise KeyError("Namespace '%s' already registered" % (
				namespace))
		self.cmd_handlers[namespace] = handler

	def remove_cmd_handler(self, namespace):
		"""Remove the A/V command handler for the given namespace."""
		if namespace in self.cmd_handlers:
			del self.cmd_handlers[namespace]

	def submit_cmd(self, cmd):
		"""Forward the given A/V command to the appropriate handler."""
		namespace, subcmd = cmd.split(" ", 1)
		try:
			self.cmd_handlers[namespace](namespace, subcmd)
		except KeyError:
			# Fall back to catch-all namespace
			self.cmd_handlers[""](namespace, subcmd)

	def run(self):
		"""Run the I/O loop until aborted."""
		try:
			self.start()
		except KeyboardInterrupt:
			print "Aborted by Ctrl-C"

		self.close()
		return 0
