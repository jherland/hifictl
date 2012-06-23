#!/usr/bin/env python2

import os
import atexit
import select

from av_device import AV_Device


class AV_FIFO(AV_Device):
	"""Encapsulate a FIFO device for receiving A/V commands.

	Receive A/V commands on the given FIFO path, and forward them to the
	A/V controller.
	"""

	Description = "A/V command FIFO"

	def __init__(self, cmd_namespace = "fifo", path = "/tmp/av_fifo"):
		AV_Device.__init__(self, cmd_namespace)

		self.path = path
		# Open FIFO for reading commands from clients
		if os.path.exists(self.path):
			raise OSError(
				"%s exists. Another instance of %s running?" % (
					self.path, self.__class__.__name__))
		os.mkfifo(self.path)
		atexit.register(self.destroy)
		self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
		self.f = os.fdopen(self.fd, "r")

	def destroy(self):
		print "Bye!"
		try:
			os.remove(self.path)
		except:
			pass

	def register(self, epoll, cmd_dispatcher):
		self.cmd_dispatcher = cmd_dispatcher
		epoll.register(self.fd, select.EPOLLIN | select.EPOLLET)
		return self.fd

	def handle_events(self, epoll, events, ts = 0):
		if not events & select.EPOLLIN:
			return # Skip non-read events
		cmds = self.f.read().split("\n")
		for cmd in cmds:
			cmd = cmd.strip()
			if cmd:
				self.debug(ts, "Received command '%s'" % (cmd))
				self.cmd_dispatcher(cmd)


def main(args):
	fifo = AV_FIFO()
	epoll = select.epoll()
	def cmd_dispatcher(cmd):
		print "cmd_dispatcher(%s)" % (cmd)
	fifo.register(epoll, cmd_dispatcher)
	print "Write commands to %s (Ctrl-C here to stop me)" % (fifo.path)
	try:
		while True:
			for fd, events in epoll.poll():
				assert fd == fifo.fd
				fifo.handle_events(epoll, events)
	except KeyboardInterrupt:
		print "Aborted by user"

	epoll.close()
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
