#!/usr/bin/env python2

import os
from tornado.web import RequestHandler, Application, StaticFileHandler

from av_device import AV_Device


class AV_CommandHandler(RequestHandler):

	def get(self, path):
		# Turn self.path into an A/V command and submit it
		cmd = path.strip("/").replace("/", " ")
		self.application.av_loop.submit_cmd(cmd)

		self.write("Received command '%s'" % (cmd))


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
		static_root = av_loop.args['%s_root' % (self.name)]
		Application.__init__(self, [
			(r"/static/(.*)",   StaticFileHandler,
				{"path": static_root}),
			(r"/(favicon.ico)", StaticFileHandler,
				{"path": static_root}),
			(r"/(.*)",          AV_CommandHandler),
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

	def cmd_catch_all(cmd, rest):
		print " -> cmd_catch_all(%s, %s)" % (cmd, rest)
	mainloop.add_cmd_handler("", cmd_catch_all)

	print "Browse to http://%s:%u/ (Ctrl-C here to stop me)" % (
		httpd.server_host or "localhost", httpd.server_port)
	return mainloop.run()


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
