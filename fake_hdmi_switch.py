#!/usr/bin/env python3

import asyncio
import logging
import serial_asyncio


logger = logging.getLogger(__name__)


class Fake_Marmitek_HDMI_Switch:
    """Impersonate a Marmitek Connect411 HDMI switch.

    Receive commands and send output identical to what we'd expect
    from the RS-232 interface of the Marmitek Connect411 HDMI switch.
    """

    responses = {
        "_power_on": (
            b"\n\r\n\rCommand Line Interface for Connect411 HDMI switch. "
            b"Copyright (c) 2008\n\rMarmitek BV, The Netherlands. "
            b"All rights reserved. www.marmitek.com\n\r>"),
        "_invalid": b"\n\n\r\rInvalid Command!\r\n",

        b"1": b"",
        b"2": b"",
        b"3": b"",
        b"4": b"",
        b"5": b"",
        b"v": (
            b"\n\r\n\rCommand Line Interface for Connect411 HDMI switch. "
            b"Copyright (c) 2008\n\rMarmitek BV, The Netherlands. "
            b"All rights reserved. www.marmitek.com\n\r\n\r"
            b"4 x 1 HDMI switch + Audio out\n\rVersion: 1.0\n\r"),
        b"?": (
            b"Command Line Interface Help:\n\r====================="
            b"======================================================\n\r"
            b"   1     Switch to Port 1\n\r"
            b"   2     Switch to Port 2\n\r"
            b"   3     Switch to Port 3\n\r"
            b"   4     Switch to Port 4\n\r"
            b"   5     Power On / Off\n\r"
            b"   v     H/W and S/W Version\n\r"
            b"   help  Command list\n\r"
            b"   ?\n\r"),
    }

    @classmethod
    async def create(cls, url, baudrate=19200, *args, **kwargs):
        reader, writer = await serial_asyncio.open_serial_connection(
            url=url, baudrate=baudrate, *args, **kwargs
        )
        return cls(reader, writer)

    def __init__(self, incoming, outgoing):
        self.incoming = incoming
        self.outgoing = outgoing
        self.pending = asyncio.Queue(maxsize=1)  # Command in-progress

    def __str__(self):
        return f"Fake HDMI switch on {self.outgoing.transport.serial.name}"

    async def power_on(self):
        logger.info("Powering on")
        await self.send(self.responses["_power_on"])

    async def send(self, data):
        logger.debug(f"out: {data!r}")
        self.outgoing.write(data)
        await self.outgoing.drain()

    async def repl(self):
        lf = b"\n\r"
        prompt = b">"
        while True:
            data = await self.incoming.readuntil(lf)
            if data == lf:  # Commands are usually preceded by lf
                try:
                    data = await asyncio.wait_for(
                        self.incoming.readuntil(lf), 0.1)
                except asyncio.TimeoutError:  # No immediate follow-up
                    await self.send(lf + prompt)
                    continue  # New line, new command
            logger.debug(f"in:  {data!r}")
            command = data.strip(lf)
            await self.send(b"\n\n\r\r" + command[0:1])
            response = self.responses.get(command, self.responses["_invalid"])
            await self.send(response)
            await self.send(prompt)


async def main(serial_port):
    hdmi = await Fake_Marmitek_HDMI_Switch.create(serial_port)
    print(f"Started {hdmi}. Press Ctrl+C to abort")
    await hdmi.power_on()
    await hdmi.repl()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=Fake_Marmitek_HDMI_Switch.__doc__)
    parser.add_argument("device", help="Serial port for HDMI switch")
    parser.add_argument(
        "--verbose", "-v", action="count", default=0, help="Increase log level"
    )
    parser.add_argument(
        "--quiet", "-q", action="count", default=0, help="Decrease log level"
    )
    args = parser.parse_args()

    loglevel = logging.WARNING + 10 * (args.quiet - args.verbose)
    logging.basicConfig(level=loglevel)

    try:
        asyncio.run(main(args.device))
    except KeyboardInterrupt:
        print("Bye!")
