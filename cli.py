#!/usr/bin/env python3

# TODO: readline support, cmd module? asynccmd???
# TODO: Accept callable to massage input lines before posting to queue
from utils import lines_from, items_from

import asyncio
import logging
# import readline
import sys


logger = logging.getLogger(__name__)


async def cli(prompt, lines, in_f=sys.stdin, out_f=sys.stdout):
    """Provide a command-line prompt and accept lines of input.

    Each line input is put onto the 'lines' queue, and the next prompt
    is issued (after the 'lines' consumer has called .task_done()).

    When EOF is encountered, this is signalled by putting None onto the
    queue and returning immediately (without waiting for the consumer).
    """

    async def do_prompt():
        await lines.join()
        if prompt is not None:
            print(prompt, end="", file=out_f, flush=True)

    await do_prompt()
    async for line in lines_from(in_f):
        logger.debug("cli() read %s", repr(line))
        await lines.put(line.rstrip("\r\n"))
        await do_prompt()
    await lines.put(None)  # Propagate EOF
    logger.info("cli() finished")


async def main():
    interactive = sys.stdin.isatty()
    if interactive:
        print("Enter lines and watch them echo. Exit with Ctrl+D")

    async def print_lines(lines):
        async for line in items_from(lines):
            print(f"< {line}")
            lines.task_done()

    lines = asyncio.Queue()
    await asyncio.gather(
        cli("> " if interactive else None, lines), print_lines(lines)
    )

    if interactive:
        print("Bye!")


if __name__ == "__main__":
    asyncio.run(main())
