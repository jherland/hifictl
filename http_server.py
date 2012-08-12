#!/usr/bin/env python2

import os
import time
import tornado.web
from tornado.escape import xhtml_escape, url_escape

from av_device import AV_Device


class EventHandler(tornado.web.RequestHandler):

	def initialize(self):
		self.application.av_loop.add_cmd_handler(
			"avr update", self.emit_avr_update)
		self.heartbeat = None

	def on_connection_close(self):
		self.application.av_loop.remove_cmd_handler(
			"avr update", self.emit_avr_update)

	def prepare(self):
		self.set_header('Content-Type', 'text/event-stream')
		self.set_header('Cache-Control', 'no-cache')

		self.write("retry: 3000\n")
		self.emit_heartbeat()
		self.emit_avr_update()

	def reset_heartbeat(self):
		if self.heartbeat:
			self.application.av_loop.remove_timeout(self.heartbeat)
		self.heartbeat = self.application.av_loop.add_timeout(
			time.time() + 1, self.emit_heartbeat)

	def emit_heartbeat(self):
		self.write("event: heartbeat\n")
		self.write("data: %u\n\n" % (time.time()))
		self.flush()
		self.reset_heartbeat()

	def emit_avr_update(self, *args):
		self.write("event: avr_update\n")
		try:
			state = self.application.av_loop.devices["avr"].state
			for line in state.json().split("\n"):
				self.write("data: %s\n" % (line))
		except:
			self.write("data: 'null'\n") # None in JSON

		self.write("\n")
		self.flush()

	@tornado.web.asynchronous
	def get(self):
		pass


class AV_CommandHandler(tornado.web.RequestHandler):

	def get(self, path):
		# Turn self.path into an A/V command and submit it
		cmd = path.strip("/").replace("/", " ")
		self.application.av_loop.submit_cmd(cmd)

	post = get


class AV_HTTPServer(AV_Device, tornado.web.Application):

	Description = "A/V controller HTTP server"

	DefaultStaticRoot = "./http_static"

	DefaultListenHost = ""
	DefaultListenPort = 8000

	@classmethod
	def register_args(cls, name, arg_parser):
		arg_parser.add_argument("--%s-root" % (name),
			default = cls.DefaultStaticRoot,
			help = "Static document root path for %s"
				" (default: %%(default)s)" % (cls.Description),
			metavar = "DIR")
		arg_parser.add_argument("--%s-host" % (name),
			default = cls.DefaultListenHost,
			help = "Listening hostname or IP address for %s"
				" (default: %%(default)s)" % (cls.Description),
			metavar = "HOST")
		arg_parser.add_argument("--%s-port" % (name),
			default = cls.DefaultListenPort,
			help = "Listening port number for %s"
				" (default: %%(default)s)" % (cls.Description),
			metavar = "PORT")

	def __init__(self, av_loop, name):
		AV_Device.__init__(self, av_loop, name)
		self.docroot = av_loop.args['%s_root' % (self.name)]
		tornado.web.Application.__init__(self, [
			(r"/events", EventHandler),
			(r"/cmd/(.*)", AV_CommandHandler),
			(r"/", tornado.web.RedirectHandler,
				{"url": "/index.html"}),
			(r"/(.*)", tornado.web.StaticFileHandler,
				{"path": self.docroot}),
		], debug = self.Debug)

		self.server_host = av_loop.args["%s_host" % (self.name)]
		self.server_port = int(av_loop.args["%s_port" % (self.name)])
		self.listen(self.server_port, self.server_host)


def main(args):
	import argparse

	from av_loop import AV_Loop

	parser = argparse.ArgumentParser(
		description = "Communicate with " + AV_HTTPServer.Description)
	AV_HTTPServer.register_args("http", parser)

	mainloop = AV_Loop(vars(parser.parse_args(args)))
	httpd = AV_HTTPServer(mainloop, "http")

	def cmd_catch_all(empty, cmd):
		assert empty == ""
		print " -> cmd_catch_all(%s)" % (cmd)
	mainloop.add_cmd_handler("", cmd_catch_all)

	print "Browse to http://%s:%u/ (Ctrl-C here to stop me)" % (
		httpd.server_host or "localhost", httpd.server_port)
	return mainloop.run()


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
