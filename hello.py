#!/usr/bin/env python3

import asyncio
import sys
from typing import TextIO


async def stream_as_generator(stream: TextIO):
    reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()
    await loop.connect_read_pipe(lambda: reader_protocol, stream)

    while True:
        line = await reader.readline()
        if not line:  # EOF
            break
        yield line


async def cli(prompt: str, lines: asyncio.Queue, in_f: TextIO, out_f: TextIO):
    print(prompt, end="", file=out_f, flush=True)
    async for line in stream_as_generator(in_f):
        await lines.put(line)
        print(prompt, end="", file=out_f, flush=True)
    await lines.put(None)  # Signal EOF


async def command_handler(commands: asyncio.Queue):
    while True:
        line = await commands.get()
        if line is None:  # EOF
            break
        print("Command:", line)
    print("Done!")


async def main():
    commands = asyncio.Queue()
    await asyncio.gather(
        cli(">> ", commands, sys.stdin, sys.stdout), command_handler(commands)
    )


if __name__ == "__main__":
    asyncio.run(main())
