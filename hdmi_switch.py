#!/usr/bin/env python3

import asyncio
import logging
import serial_asyncio


logger = logging.getLogger(__name__)


class Marmitek_HDMI_Switch:
    """Async communication with a Marmitek Connect411 HDMI switch.

    Encapsulate RS-232 commands and responses to/from the serial port
    connected to this switch.
    """

    # Map simple string commands to corresponding HDMI switch serial commands
    codes = [  # (command name, serial port byte)
        ("1", b"1"),
        ("2", b"2"),
        ("3", b"3"),
        ("4", b"4"),
        ("on", b"5"),
        ("off", b"5"),
        ("on/off", b"5"),
        ("version", b"v"),
        ("help", b"?"),
    ]

    # Emitted by HDMI Switch on startup
    startup_message = (
        b"Marmitek BV, The Netherlands. All rights reserved. www.marmitek.com"
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
        self.rts = asyncio.Event()  # ready-to-send
        self.rts.set()
        self.logger.info(
            "Communicating via %s", self.to_tty.transport.serial.name
        )

    async def recv(self, response_queue):
        logger = self.logger.getChild("recv")
        codemap = {byte: cmd for cmd, byte in self.codes}
        while True:
            try:
                data = await self.from_tty.readuntil(b">")
            except asyncio.IncompleteReadError as e:
                logger.debug("incomplete read:")
                data = e.partial
            logger.debug(f"<<< {data!r}")
            line = data.strip(b"\r\n>")
            if line:
                try:
                    command = codemap[line[0:1]]
                    output = line[1:].lstrip(b"\r\n").decode("ascii")
                    self.rts.set()
                except KeyError:
                    command = None  # Unknown
                    output = line
                logger.info(f"received ({command}, {output})")
                await response_queue.put((command, output))
            if self.from_tty.at_eof():
                await response_queue.put(None)  # EOF
                logger.info("finished")
                break

    async def send(self, command_queue):
        logger = self.logger.getChild("send")
        lf = b"\n\r"  # Marmitek has strange newline conventions
        commands = {cmd: lf + byte + lf for cmd, byte in self.codes}
        while True:
            try:
                await asyncio.wait_for(self.rts.wait(), 1)
            except asyncio.TimeoutError:
                logger.debug("failed to get RTS, sending anyway")
            self.rts.clear()

            cmd = await command_queue.get()
            if cmd is None:  # Shutdown
                logger.info("finished")
                self.to_tty.close()
                await self.to_tty.wait_closed()
                break
            data = commands[cmd]
            logger.info(f"sending {cmd}")
            logger.debug(f">>> {data!r}")
            self.to_tty.write(data)
            await self.to_tty.drain()


async def main(serial_port):
    # TODO: print("Write HDMI switch commands to stdin (Ctrl-D to stop)")
    hdmi = await Marmitek_HDMI_Switch.create(serial_port)
    commands = asyncio.Queue()
    responses = asyncio.Queue()

    async def issue_commands(commands):
        await commands.put("on")
        await commands.put("version")
        await commands.put("help")
        await commands.put("1")
        await commands.put("2")
        await commands.put("3")
        await commands.put("4")
        await commands.put("3")
        await commands.put("2")
        await commands.put("1")
        await commands.put("off")
        await commands.put(None)

    async def print_responses(responses):
        while True:
            response = await responses.get()
            if response is None:  # shutdown
                break
            command, output = response
            print(f"> {command}")
            if output:
                print()
                print(output)
                print()

    await asyncio.gather(
        issue_commands(commands),
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
