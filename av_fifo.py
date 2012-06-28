#!/usr/bin/env python2

import os
import atexit

from av_device import AV_Device


class AV_FIFO(AV_Device):
	"""Encapsulate a FIFO device for receiving A/V commands.

	Receive A/V commands on the given FIFO path, and forward them to the
	A/V controller.
	"""

	Description = "A/V command FIFO"

	def __init__(self, av_loop, name = "fifo", path = "/tmp/av_fifo"):
		AV_Device.__init__(self, av_loop, name)

		self.path = path
		# Open FIFO for reading commands from clients
		if os.path.exists(self.path):
			raise OSError(
				"%s exists. Another instance of %s running?" % (
					self.path, self.__class__.__name__))
		os.mkfifo(self.path)
		atexit.register(self.destroy)

		self.fd = -1
		self.open()

	def open(self):
		assert self.fd == -1
		self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
		self.av_loop.add_handler(self.fd, self.handle_io,
			self.av_loop.READ)

	def close(self):
		assert self.fd >= 0
		self.av_loop.remove_handler(self.fd)
		os.close(self.fd)
		self.fd = -1

	def destroy(self):
		print "Bye!"
		try:
			os.remove(self.path)
			self.close()
		except:
			pass

	def handle_io(self, fd, events):
		assert fd == self.fd
		self.debug("handle_io(%i, %s)" % (fd, events))
		if events & self.av_loop.READ:
			cmds = os.read(self.fd, 64 * 1024).split("\n")
			for cmd in cmds:
				cmd = cmd.strip()
				if cmd:
					self.debug("recv cmd '%s'"  % (cmd))
					self.av_loop.submit_cmd(cmd)
		if events & self.av_loop.ERROR:
			# Reopen fifo to allow further commands
			self.close()
			self.open()


def main(args):
	from av_loop import AV_Loop

	mainloop = AV_Loop()

	fifo = AV_FIFO(mainloop)

	def cmd_dispatcher(namespace, subcmd):
		print " -> cmd_dispatcher(%s, %s)" % (namespace, subcmd)
	mainloop.add_cmd_handler("", cmd_dispatcher)

	print "Write commands to %s (Ctrl-C here to stop me)" % (fifo.path)
	return mainloop.run()


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
