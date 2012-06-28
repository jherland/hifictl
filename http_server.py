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

	Debug = True ###

	def __init__(self, av_loop, name = "http", static_root = "./http",
			address = ("", 8000)):
		AV_Device.__init__(self, av_loop, name)
		Application.__init__(self, [
			(r"/static/(.*)",   StaticFileHandler,
				{"path": static_root}),
			(r"/(favicon.ico)", StaticFileHandler,
				{"path": static_root}),
			(r"/(.*)",          AV_CommandHandler),
		], debug = self.Debug)

		self.address = address
		self.listen(self.address[1], self.address[0])


def main(args):
	from av_loop import AV_Loop

	mainloop = AV_Loop()

	httpd = AV_HTTPServer(mainloop)

	def cmd_dispatcher(namespace, subcmd):
		print " -> cmd_dispatcher(%s, %s)" % (namespace, subcmd)
	mainloop.add_cmd_handler("", cmd_dispatcher)

	print "Browse to http://%s:%u/ (Ctrl-C here to stop me)" % (
		httpd.address[0] or "localhost", httpd.address[1])
	return mainloop.run()


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
