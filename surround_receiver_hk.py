#!/usr/bin/env python3

import asyncio
import logging
import serial_asyncio

import avr_dgram
from avr_status import AVR_Status


logger = logging.getLogger(__name__)


class HarmanKardon_Surround_Receiver:
    """Async communication with a Harman/Kardon AVR 430 surround receiver.

    Encapsulate RS-232 commands and responses to/from the serial port
    connected to this receiver.
    """

    in_spec = avr_dgram.AVR_PC_Status
    out_spec = avr_dgram.PC_AVR_Command
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

    @classmethod
    async def create(cls, url, baudrate=38400, *args, **kwargs):
        reader, writer = await serial_asyncio.open_serial_connection(
            url=url, baudrate=baudrate, *args, **kwargs
        )
        return cls(reader, writer)

    def __init__(self, from_tty, to_tty):
        self.logger = logger.getChild(self.__class__.__name__)
        self.from_tty = from_tty
        self.to_tty = to_tty
        self.pending = asyncio.Queue(maxsize=1)  # Command in-progress
        self.logger.info(
            "Communicating via %s", self.to_tty.transport.serial.name
        )

    def parse_dgram(self, dgram):
        try:
            return AVR_Status.parse(avr_dgram.parse(dgram, self.in_spec))
        except ValueError:
            return None

    async def recv(self, response_queue):
        """Read commands and their responses from the HDMI switch.

        Put corresponding Response objects onto the 'response_queue'.
        If EOF is received over the serial port, put None as a sentinel
        onto the 'response_queue' and exit immediately.
        """
        logger = self.logger.getChild("recv")
        while True:
            try:
                dgram = await self.from_tty.read(
                    avr_dgram.dgram_len(self.in_spec))
            except asyncio.IncompleteReadError as e:
                logger.debug("incomplete read:")
                dgram = e.partial
            logger.debug(f"<<< {dgram!r}")
            status = self.parse_dgram(dgram)
            if status is not None:
                logger.info(f"received {status}")
                await response_queue.put(status)
                await response_queue.join()
            if self.from_tty.at_eof():
                await response_queue.put(None)  # EOF
                logger.info("finished")
                break

    async def send(self, command_queue):
        """Write receiver commands from 'command_queue' to the serial port."""
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
            except KeyError:
                if cmd:
                    logger.error(f"Unknown command {cmd!r}")
            else:
                logger.info(f"sending {cmd!r}")
                logger.debug(f">>> {data!r}")
                self.to_tty.write(data)
                await self.to_tty.drain()
                try:
                    await asyncio.wait_for(self.pending.put(cmd), 3)
                except asyncio.TimeoutError:
                    logger.warning(f"Pending timeout (previous)!")
                else:
                    try:
                        await asyncio.wait_for(self.pending.join(), 3)
                    except asyncio.TimeoutError:
                        logger.warning(f"Pending timeout (current)!")
            command_queue.task_done()


async def main(serial_port):
    from cli import cli

    surround = await HarmanKardon_Surround_Receiver.create(serial_port)
    commands = asyncio.Queue()
    responses = asyncio.Queue()

    print("Write surround receiver commands to stdin (Ctrl-D to stop).")
    print("Available commands:")
    for cmd in surround.codes.keys():
        print(f"    {cmd}")
    print()

    async def print_responses(responses):
        while True:
            s = await responses.get()
            if s is None:  # shutdown
                print("Bye!")
                break
            print(s)
            responses.task_done()

    await asyncio.gather(
        cli("surround> ", commands),
        surround.send(commands),
        surround.recv(responses),
        print_responses(responses),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=HarmanKardon_Surround_Receiver.__doc__
    )
    parser.add_argument(
        "--device",
        "-D",
        default="/dev/ttyUSB1",
        help="Serial port for surround receiver (default: /dev/ttyUSB1)",
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
