#!/usr/bin/env python2

import os
import select
import time
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

from av_device import AV_Device


class AV_ReqHandler(BaseHTTPRequestHandler):

	server_version = "AV_httpd/0.1"

	StaticPaths = {
		"/favicon.ico": "image/x-icon"
	}

	def do_static(self):
		content_type = self.StaticPaths[self.path]

		self.send_response(200)
		self.send_header("Content-Type", content_type)
		self.end_headers()

		f = open(os.path.join(self.server.root, self.path.lstrip("/")))
		self.wfile.write(f.read())
		f.close()

	def do_GET(self):
		if self.path in self.StaticPaths:
			return self.do_static()

		# Turn self.path into an A/V command and submit it
		cmd = self.path.strip("/").replace("/", " ")
		self.server.cmd_dispatcher(cmd)

		# Send data back to the client
		self.send_response(200)
		self.send_header("Content-Type", "text/plain")
		self.end_headers()

		print >>self.wfile, self.server, self.server.cookie
		print >>self.wfile, self.path, "->", cmd


class AV_HTTPServer(HTTPServer, AV_Device):

	Description = "A/V controller HTTP server"

	def __init__(self, cmd_namespace = "http", root = "./http",
		     address = ('', 8000), ReqHandlerClass = AV_ReqHandler):
		HTTPServer.__init__(self, address, ReqHandlerClass)
		AV_Device.__init__(self, cmd_namespace)

		self.root = root
		self.cookie = 0

	def register(self, epoll, cmd_dispatcher):
		self.cmd_dispatcher = cmd_dispatcher
		epoll.register(self.fileno(), select.EPOLLIN)
		return self.fileno()

	def handle_events(self, epoll, events, ts = 0):
		if events & select.EPOLLIN:
			self.cookie = ts
#			t_start = time.time()
			self.handle_request()
#			elapsed = time.time() - t_start
#			self.debug(ts, "Handled request in %.2fs" % (elapsed))
		events &= ~select.EPOLLIN
		if events:
			self.debug(ts, "Unhandled events: %u" % (events))


def main(args):
	httpd = AV_HTTPServer()
	epoll = select.epoll()

	def cmd_dispatcher(cmd):
		print "cmd_dispatcher(%s)" % (cmd)

	httpd.register(epoll, cmd_dispatcher)
	print "Browse to %s:%u (Ctrl-C here to stop me)" % (
		httpd.server_name, httpd.server_port)

	t_start = time.time()
	ts = 0
	try:
		while True:
			for fd, events in epoll.poll():
				ts = time.time() - t_start
				assert fd == httpd.fileno()
				httpd.handle_events(epoll, events, ts)
	except KeyboardInterrupt:
		print "Aborted by user"

	epoll.close()
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
