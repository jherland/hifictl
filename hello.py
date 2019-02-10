#!/usr/bin/env python3

import asyncio
import sys


async def stream_as_generator(stream):
    reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()
    await loop.connect_read_pipe(lambda: reader_protocol, stream)

    while True:
        line = await reader.readline()
        if not line:  # EOF
            break
        yield line


async def cli(prompt, in_f=sys.stdin, out_f=sys.stdout):
    print(prompt, end="", file=out_f, flush=True)
    async for line in stream_as_generator(in_f):
        yield line
        print(prompt, end="", file=out_f, flush=True)


async def main():
    async for command in cli(">> "):
        print("Command:", command)
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
