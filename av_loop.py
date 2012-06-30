#!/usr/bin/env python2

import time
from tornado.ioloop import IOLoop

class AV_Loop(IOLoop):
	
	def __init__(self, parsed_args):
		IOLoop.__init__(self)
		self.install()

		self.args = parsed_args
		self.t0 = time.time() # Keep track of when we started

		self.cmd_handlers = {} # Map commands to command handlers

	def add_cmd_handler(self, cmd, handler):
		"""Registers the given handler to receive the given A/V command.

		A/V commands are strings made up of whitespace-separated words.
		By registering a handler for a given string "$word1 $word2...",
		that handler will be invoked for any command that starts with
		"$word1 $word2..." (unless a more specific matching handler is
		also registered). E.g. given the following cmd_handlers map: {
		  "foo bar": foo_bar,
		  "foo": foo,
		  "": catch_all,
		}, the following describes which commands will invoke which
		functions:
		  - "foo bar baz" -> foo_bar("foo bar", "baz")
		  - "foo bar" -> foo_bar("foo bar", "")
		  - "foo baz" -> foo("foo", "baz")
		  - "foo" -> foo("foo", "")
		  - "bar" -> catch_all("", "bar")
		  - "foo barf" -> foo("foo", "barf")

		The given handler will be invoked with two arguments, the first
		is the cmd which matched its registration, and the second is
		the remainder of the command that followed the match.
		"""
		if cmd in self.cmd_handlers:
			raise KeyError("Command '%s' already registered" % cmd)
		self.cmd_handlers[cmd] = handler

	def remove_cmd_handler(self, cmd):
		"""Remove the A/V command handler for the given A/V command."""
		if cmd in self.cmd_handlers:
			del self.cmd_handlers[cmd]

	def submit_cmd(self, cmd):
		"""Forward the given A/V command to the appropriate handler.

		See the documentation of add_cmd_handler() to see how commands
		are mapped to handlers.
		"""
		pre_words = cmd.strip().split()
		post_words = []
		while pre_words:
			pre_cmd = " ".join(pre_words)
			if pre_cmd in self.cmd_handlers:
				return self.cmd_handlers[pre_cmd](
					pre_cmd, " ".join(post_words))
			post_words.insert(0, pre_words.pop())
		return self.cmd_handlers[""]("", " ".join(post_words))

	def run(self):
		"""Run the I/O loop until aborted."""
		try:
			self.start()
		except KeyboardInterrupt:
			print "Aborted by Ctrl-C"

		self.close()
		return 0
