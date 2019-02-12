import asyncio
import codecs
import locale


class TextStreamReader:
    """Wrap a (binary) StreamReader with text decoding.

    This is to StreamReader what TextIOWrapper is to BufferedIOBase."""

    def __init__(self, raw_reader, encoding=None, errors="strict"):
        if encoding is None:
            encoding = locale.getpreferredencoding(False)
        self.raw_reader = raw_reader
        self.encoding = encoding
        self.errors = errors
        self.decoder = codecs.getincrementaldecoder(encoding)(errors=errors)

    async def read(self, n=-1):
        data = await self.raw_reader.read(n)
        return self.decoder.decode(data)

    async def readline(self):
        data = await self.raw_reader.readline()
        return self.decoder.decode(data)

    async def readexactly(self, n):
        data = await self.raw_reader.readexactly(n)
        return self.decoder.decode(data)

    async def readuntil(self, separator="\n"):
        encoded_sep = codecs.encode(separator, self.encoding, self.errors)
        data = await self.raw_reader.readuntil(encoded_sep)
        return self.decoder.decode(data)

    def __getattr__(self, name):
        return getattr(self.raw_reader, name)


async def lines_from(stream):
    """Allow 'async for line in lines_from(stream)'."""
    # loop.connect_read_pipe() drills straight into a stream's .fileno(), and
    # hooks that up to a StreamReader object. This will ignore/bypass any
    # TextIOWrapper on that stream, so in that case we set up a corresponding
    # TextStreamReader so that we can yield text instead of bytes.
    reader = asyncio.StreamReader()
    if hasattr(stream, "encoding") and hasattr(stream, "errors"):
        reader = TextStreamReader(reader, stream.encoding, stream.errors)
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()
    await loop.connect_read_pipe(lambda: reader_protocol, stream)

    while True:
        line = await reader.readline()
        if not line:  # EOF
            break
        yield line


async def items_from(queue):
    """Allow 'async for item in items_from(queue)'.

    Iteration ends at the first item that is None."""
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
