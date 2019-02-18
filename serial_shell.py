#!/usr/bin/env python3
"""Simple serial port shell.

Read lines from stdin and send them to the serial port. Read bytes from the
serial port and print them to stdout.
"""

import argparse
import asyncio
import cli
import serial_asyncio
import sys


async def send(messages, pipe):
    """Consume messages and write them to pipe."""
    while True:
        msg = await messages.get()
        if msg is None:  # Shutdown
            pipe.close()
            await pipe.wait_closed()
            break
        msg = msg.encode() + b"\r\n"
        pipe.write(msg)
        await pipe.drain()
        messages.task_done()


async def recv(messages, pipe):
    """Read bytes from pipe and produce messages."""
    while True:
        try:
            data = await pipe.read(128)
        except asyncio.IncompleteReadError as e:
            data = e.partial
        await messages.put(data)
        await messages.join()
        if pipe.at_eof():
            await messages.put(None)  # EOF
            break


async def print_bytes(messages):
    while True:
        msg = await messages.get()
        if msg is None:  # shutdown
            break
        print(f"<<< {len(msg)} bytes: {msg!r}")
        messages.task_done()


async def main(serial_port, baudrate):

    read_pipe, write_pipe = await serial_asyncio.open_serial_connection(
            url=serial_port, baudrate=baudrate)

    lines_to_device = asyncio.Queue()
    bytes_from_device = asyncio.Queue()

    await asyncio.gather(
        cli.cli("> ", lines_to_device),
        send(lines_to_device, write_pipe),
        recv(bytes_from_device, read_pipe),
        print_bytes(bytes_from_device),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", help="Serial port to open")
    parser.add_argument("baudrate", type=int, help="Baud rate")
    args = parser.parse_args()

    asyncio.run(main(args.device, args.baudrate))
