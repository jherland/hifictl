#!/usr/bin/env python

import time
import tornado.web

from av_device import AV_Device


class EventHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.application.av_loop.add_cmd_handler("avr update", self.emit_avr_update)
        self.heartbeat = None

    def on_connection_close(self):
        self.application.av_loop.remove_cmd_handler("avr update", self.emit_avr_update)
        if self.heartbeat:
            self.heartbeat.stop()
            self.heartbeat = None

    def prepare(self):
        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        # Instruct clients to reconnect if they lose the connection
        self.write("retry: 3000\n")
        # Also send a periodic heartbeat to the client, so they can
        # detect disconnection even if their browser (e.g. Opera)
        # does not.
        self.heartbeat = tornado.ioloop.PeriodicCallback(self.emit_heartbeat, 3000)
        self.heartbeat.start()

    def emit_heartbeat(self):
        self.write("event: heartbeat\n")
        self.write("data: %u\n\n" % (time.time()))
        self.flush()

    def emit_avr_update(self, *args):
        self.write("event: avr_update\n")
        try:
            state = self.application.av_loop.devices["avr"].state
            for line in state.json().split("\n"):
                self.write("data: %s\n" % (line))
        except:
            self.write("data: 'null'\n")  # None in JSON

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
        arg_parser.add_argument(
            "--%s-root" % (name),
            default=cls.DefaultStaticRoot,
            metavar="DIR",
            help="Static document root path for %s"
            " (default: %%(default)s)" % (cls.Description),
        )
        arg_parser.add_argument(
            "--%s-host" % (name),
            default=cls.DefaultListenHost,
            metavar="HOST",
            help="Listening hostname or IP address for %s"
            " (default: %%(default)s)" % (cls.Description),
        )
        arg_parser.add_argument(
            "--%s-port" % (name),
            default=cls.DefaultListenPort,
            metavar="PORT",
            help="Listening port number for %s"
            " (default: %%(default)s)" % (cls.Description),
        )

    def __init__(self, av_loop, name):
        AV_Device.__init__(self, av_loop, name)
        self.docroot = av_loop.args["%s_root" % (self.name)]
        tornado.web.Application.__init__(
            self,
            [
                (r"/events", EventHandler),
                (r"/cmd/(.*)", AV_CommandHandler),
                (r"/", tornado.web.RedirectHandler, {"url": "/index.html"}),
                (r"/(.*)", tornado.web.StaticFileHandler, {"path": self.docroot}),
            ],
            debug=self.Debug,
        )

        self.server_host = av_loop.args["%s_host" % (self.name)]
        self.server_port = int(av_loop.args["%s_port" % (self.name)])
        self.listen(self.server_port, self.server_host)


def main(args):
    import argparse
    from tornado.ioloop import IOLoop

    from av_loop import AV_Loop

    parser = argparse.ArgumentParser(
        description="Communicate with " + AV_HTTPServer.Description
    )
    AV_HTTPServer.register_args("http", parser)

    IOLoop.configure(AV_Loop, parsed_args=vars(parser.parse_args(args)))
    mainloop = IOLoop.instance()
    httpd = AV_HTTPServer(mainloop, "http")

    def cmd_catch_all(empty, cmd):
        assert empty == ""
        print(" -> cmd_catch_all(%s)" % (cmd))

    mainloop.add_cmd_handler("", cmd_catch_all)

    print(
        "Browse to http://%s:%u/ (Ctrl-C here to stop me)"
        % (httpd.server_host or "localhost", httpd.server_port)
    )
    return mainloop.run()


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
