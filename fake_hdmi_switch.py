#!/usr/bin/env python

import os

from fake_serial_device import Fake_SerialDevice


class Fake_HDMI_Switch(Fake_SerialDevice):
    """Impersonate a HDMI switch.

    Receive remote commands, update internal state and provide
    plausible responses.
    """

    Description = "Fake Marmitek Connect411 HDMI switch"

    # Marmitek has strange newline conventions
    LF = "\n\r"

    def __init__(self, av_loop, name):
        Fake_SerialDevice.__init__(self, av_loop, name)

    def handle_read(self):
        data = os.read(self.master, len(self.LF) * 2 + 1)
        cmd = data.strip()
        self.debug("Received '%s'" % (cmd))
        output = "Unknown Command!"
        if cmd in ("1", "2", "3", "4", "5"):
            output = cmd
        if cmd == "v":
            # FIXME: More output
            output = "Marmitek BV, The Netherlands. " \
                "All rights reserved. www.marmitek.com"
        if cmd == "?":
            # FIXME: output
            output = "???"
        os.write(self.master, output + self.LF + ">")


def main(args):
    import argparse
    from tornado.ioloop import IOLoop

    from av_loop import AV_Loop

    parser = argparse.ArgumentParser(
        description=Fake_HDMI_Switch.Description)
    Fake_HDMI_Switch.register_args("hdmi", parser)

    IOLoop.configure(AV_Loop, parsed_args=vars(parser.parse_args(args)))
    mainloop = IOLoop.instance()
    hdmi = Fake_HDMI_Switch(mainloop, "hdmi")

    print("You can now start ./av_control.py --hdmi-tty %s" % (
        hdmi.client_name()))

    return mainloop.run()


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
