#!/usr/bin/env python3

from utils import lines_from, items_from

import asyncio
import logging
import sys


logger = logging.getLogger(__name__)


async def cli(prompt, lines, in_f=sys.stdin, out_f=sys.stdout):
    def do_prompt():
        if prompt is not None:
            print(prompt, end="", file=out_f, flush=True)

    loop = asyncio.get_event_loop()
    loop.call_soon(do_prompt)
    async for line in lines_from(in_f):
        logger.debug("cli() read %s", repr(line))
        await lines.put(line.rstrip("\r\n"))
        loop.call_soon(do_prompt)
    await lines.put(None)  # Propagate EOF
    logger.info("cli() finished")


async def main():
    interactive = sys.stdin.isatty()
    if interactive:
        print("Enter lines and watch them echo. Exit with Ctrl+D")

    async def print_lines(lines):
        async for line in items_from(lines):
            print(f"< {line}")

    lines = asyncio.Queue()
    await asyncio.gather(
        cli("> " if interactive else None, lines), print_lines(lines)
    )

    if interactive:
        print("Bye!")


if __name__ == "__main__":
    asyncio.run(main())
