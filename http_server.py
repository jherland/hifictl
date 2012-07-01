#!/usr/bin/env python2

import os
from tornado.web import RequestHandler, Application, StaticFileHandler, asynchronous
from tornado.escape import xhtml_escape, url_escape
from tornado.template import Loader

from av_device import AV_Device


class IndexHandler(RequestHandler):

	def get(self, path):
		app = self.application

		try:
			avr_state = app.av_loop.devices["avr"].state
		except KeyError:
			avr_state = None

		self.write(app.templates.load("index.html").generate(
			title = app.Description,
			avr_state = avr_state,
			cmd_handlers = app.av_loop.cmd_handlers,
			last_cmd = self.get_argument("cmd", None),
		))


class EventHandler(RequestHandler):

	def initialize(self):
		self.application.av_loop.add_cmd_handler(
			"avr update", self.emit)

	def on_connection_close(self):
		self.application.av_loop.remove_cmd_handler(
			"avr update", self.emit)

	def prepare(self):
		self.set_header('Content-Type', 'text/event-stream')
		self.set_header('Cache-Control', 'no-cache')

		self.emit()

	def emit(self, *args):
		try:
			avr_state = self.application.av_loop.devices["avr"].state
			self.write("data: %s" % (avr_state))
		except:
			self.write("data: Failed to get AVR_State...")

		self.write("\n\n")
		self.flush()

	@asynchronous
	def get(self):
		pass

class AV_CommandHandler(RequestHandler):

	def get(self, path):
		# Turn self.path into an A/V command and submit it
		cmd = path.strip("/").replace("/", " ")
		self.application.av_loop.submit_cmd(cmd)

		# Redirect back to index
		self.redirect("/?cmd=%s" % (url_escape(cmd)))


class AV_HTTPServer(AV_Device, Application):

	Description = "A/V controller HTTP server"

	DefaultStaticRoot = "./http"

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
		Application.__init__(self, [
			(r"/(static/.*)",   StaticFileHandler,
				{"path": self.docroot}),
			(r"/(favicon.ico)", StaticFileHandler,
				{"path": self.docroot}),
			(r"/(index.html)?", IndexHandler),
			(r"/events",        EventHandler),
			(r"/(.*)",          AV_CommandHandler),
		], debug = self.Debug)

		# Template loader (and cache)
		self.templates = Loader(os.path.join(self.docroot, "templates"))

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
