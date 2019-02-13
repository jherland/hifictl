#!/usr/bin/env python3

import asyncio
from dataclasses import dataclass
import logging
import serial_asyncio
from typing import Optional


logger = logging.getLogger(__name__)


class Marmitek_HDMI_Switch:
    """Async communication with a Marmitek Connect411 HDMI switch.

    Encapsulate RS-232 commands and responses to/from the serial port
    connected to this switch.
    """

    # Map simple string commands to corresponding HDMI switch serial commands
    codes = {  # (command name, serial port byte)
        "1": b"1",
        "2": b"2",
        "3": b"3",
        "4": b"4",
        "on": b"5",
        "off": b"5",
        "on/off": b"5",
        "version": b"v",
        "help": b"?",
    }

    # Emitted by HDMI Switch when power is supplied
    startup_message = (
        b"Command Line Interface for Connect411 HDMI switch. "
        b"Copyright (c) 2008\n\rMarmitek BV, The Netherlands. "
        b"All rights reserved. www.marmitek.com"
    )

    @classmethod
    async def create(cls, url, baudrate=19200, *args, **kwargs):
        reader, writer = await serial_asyncio.open_serial_connection(
            url=url, baudrate=baudrate, *args, **kwargs
        )
        return cls(reader, writer)

    def __init__(self, from_tty, to_tty):
        self.logger = logger.getChild(self.__class__.__name__)
        self.from_tty = from_tty
        self.to_tty = to_tty
        self.pending = asyncio.Queue(maxsize=1)  # Command in-progress
        self.logger.info("Communicating via %s", self.to_tty.transport.serial.name)

    @dataclass
    class Response:
        """Encapsulate a serial port response from the HDMI switch."""

        command: Optional[str]  # Command that caused this response, or None
        body: Optional[str]  # The decoded response body, if any
        raw_body: bytes  # The raw response body
        expected: bool  # True iff this response was caused by send()

    def parse_response(self, data):
        """Parse response bytes from serial port into Response.object."""
        data = data.strip(b"\r\n>")
        if not data:
            return None

        command, expected = None, False
        cmdbyte = data[0:1]
        try:
            pending_command = self.pending.get_nowait()
        except asyncio.QueueEmpty:  # No pending command
            pass
        else:
            self.pending.task_done()
            if cmdbyte == self.codes[pending_command]:
                # Assume this is the response to the last-sent command
                command, expected = pending_command, True

        if command is None:
            # Guess command from cmdbyte
            codes_revmap = {byte: cmd for cmd, byte in self.codes.items()}
            command = codes_revmap.get(cmdbyte)

        if command:  # cmdbyte is valid, pop it off the incoming bytes
            data = data[1:].lstrip(b"\r\n")

        try:
            body = data.decode("ascii")
        except Exception:
            body = None
        return self.Response(command, body, data, expected)

    # TODO: Fix when HDMI switch is OFF and nothing is received. (timeout?)
    async def recv(self, response_queue):
        """Read commands and their responses from the HDMI switch.

        Put corresponding Response objects onto the 'response_queue'.
        If EOF is received over the serial port, put None as a sentinel
        onto the 'response_queue' and exit immediately.
        """
        logger = self.logger.getChild("recv")
        while True:
            # The '>' char is exclusively used as the serial port prompt char
            # Use it to distinguish response boundaries.
            try:
                data = await self.from_tty.readuntil(b">")
            except asyncio.IncompleteReadError as e:
                logger.debug("incomplete read:")
                data = e.partial
            logger.debug(f"<<< {data!r}")
            response = self.parse_response(data)
            if response:
                logger.info(f"received {response}")
                await response_queue.put(response)
                await response_queue.join()
            if self.from_tty.at_eof():
                await response_queue.put(None)  # EOF
                logger.info("finished")
                break

    async def send(self, command_queue):
        """Issue switch commands from 'command_queue' over the serial port."""
        logger = self.logger.getChild("send")
        lf = b"\n\r"  # Marmitek has strange newline conventions
        while True:
            cmd = await command_queue.get()
            if cmd is None:  # Shutdown
                logger.info("finished")
                self.to_tty.close()
                await self.to_tty.wait_closed()
                break
            try:
                data = lf + self.codes[cmd] + lf
                logger.info(f"sending {cmd!r}")
                logger.debug(f">>> {data!r}")
                self.to_tty.write(data)
                await self.to_tty.drain()
                await self.pending.put(cmd)
                await self.pending.join()
            except KeyError:
                if cmd:
                    logger.error(f"Unknown command {cmd!r}")
            command_queue.task_done()


async def main(serial_port):
    from cli import cli

    hdmi = await Marmitek_HDMI_Switch.create(serial_port)
    commands = asyncio.Queue()
    responses = asyncio.Queue()

    print("Write HDMI switch commands to stdin (Ctrl-D to stop).")
    print("Available commands:")
    for cmd in hdmi.codes.keys():
        print(f"    {cmd}")
    print()

    async def print_responses(responses):
        while True:
            r = await responses.get()
            if r is None:  # shutdown
                print("Bye!")
                break
            r_type = "<" if r.expected else "\n*"
            print(f"{r_type} {r.command}")
            if r.body:
                print()
                print(r.body)
                print()
            responses.task_done()

    await asyncio.gather(
        cli("hdmi> ", commands),
        hdmi.send(commands),
        hdmi.recv(responses),
        print_responses(responses),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=Marmitek_HDMI_Switch.__doc__)
    parser.add_argument(
        "--device",
        "-D",
        default="/dev/ttyUSB0",
        help="Serial port for HDMI switch (default: /dev/ttyUSB0)",
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=0, help="Increase log level"
    )
    parser.add_argument(
        "--quiet", "-q", action="count", default=0, help="Decrease log level"
    )
    args = parser.parse_args()

    loglevel = logging.WARNING + 10 * (args.quiet - args.verbose)
    logging.basicConfig(level=loglevel)

    asyncio.run(main(args.device))
