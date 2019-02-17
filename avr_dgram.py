"""Low-level datagram en/decoding for the Harman/Kardon AVR protocol."""

# Datagram spec for AVR->PC status updated
AVR_PC_Status = (b"MPSEND", 3, 48)

# Datagram spec for PC->AVR remote control commands
PC_AVR_Command = (b"PCSEND", 2, 4)


def calc_cksum(data):
    """Return the two-byte checksum calculated from the given data.

    The checksum algorithm XORs the bytes at even/odd indices, and
    stores the result in the first/second byte of the return value.
    """
    cksum = [0, 0]
    for i, b in enumerate(data):
        cksum[i % 2] ^= b
    return bytes(cksum)


def dgram_len(dgram_spec):
    """Return the total number of bytes in an AVR datagram of the given spec.

    The spec is given as a (keyword, type, length) tuple. The datagram length
    (incl. protocol overhead) is returned. A datagram is structured as follows:
     - Start keyword (== keyword), len(keyword) bytes
     - Data type (== type), 1 byte
     - Data length (== length), 1 byte
     - Data, 'length' bytes
     - Checksum, 2 bytes
    """
    keyword, type, length = dgram_spec
    return len(keyword) + 1 + 1 + length + 2


def initial_bytes(dgram_spec):
    """Return the initial bytes of an AVR datagram according to the given spec.

    This consists of the start keyword, followed by two bytes specifying the
    type and length.
    """
    keyword, type, length = dgram_spec
    return keyword + bytes([type, length])


def parse(dgram, dgram_spec):
    """Parse the given datagram according to the given spec and return its data.

    The datagram is parsed according to the given spec, which is a
    (keyword, type, length) tuple specifying the expected datagram type and
    length (not including the 10-byte protocol overhead).

    Usually, this class handles status updates from the AVR side, in which case
    dgram_spec should be ("MPSEND", 3, 48). Otherwise, for parsing datagrams
    containing remote control commands to the AVR, dgram_spec should be
    ("PCSEND", 2, 4).

    AVR datagrams are structured as follows:
     - 6 bytes:  Transmission keyword in ASCII (keyword)
     - "MPSEND": AVR -> PC
     - "PCSEND": PC -> AVR
     - 1 byte:   Data Type (type)
       - 0x01: DSP UPGRADE (PC -> AVR)
       - 0x02: PC Remote controller (PC -> AVR)
       - 0x03: Status data from AVR (AVR -> PC)
       - 0x04: CPU UPGRADE (PC -> AVR)
     - 1 byte:   Data Length (length)
     - N bytes:  Data (N == length)
     - 2 bytes:  Checksum:
       - First byte: XOR of all even bytes in data
       - Second byte: XOR of all odd bytes in data

    See the H/K AVR RS-232 protocol documentation for more details.
    """
    keyword, type, length = dgram_spec
    full_length = dgram_len(dgram_spec)

    if not isinstance(dgram, bytes):
        raise ValueError(f"Given datagram is not a bytes object ({dgram!r})")
    if len(dgram) != full_length:
        raise ValueError(f"Unexpected datagram length ({len(dgram)})")
    if not dgram.startswith(keyword):
        raise ValueError(f"Unexpected start keyword ({dgram[:len(keyword)]})")
    if dgram[6] != type:
        raise ValueError(f"Unexpected type ({dgram[6]} != {type})")
    if dgram[7] != length:
        raise ValueError(f"Unexpected data length ({dgram[7]} != {length})")
    data = dgram[8 : 8 + length]
    cksum = dgram[8 + length :]
    if calc_cksum(data) != cksum:
        raise ValueError(f"Failed checksum ({calc_cksum(data)} != {cksum})")
    return data


def build(data, dgram_spec):
    """Embed the given data in a datagram of the given dgram_spec.

    Return the full datagram, including protocol overhead.
    """
    keyword, type, length = dgram_spec
    if not isinstance(data, bytes):
        raise ValueError(f"Given data is not a bytes object ({data!r})")
    if len(data) != length:
        raise ValueError(f"Incorrect data length ({len(data)} != {length})")
    return keyword + bytes([type, length]) + data + calc_cksum(data)
