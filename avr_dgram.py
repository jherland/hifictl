#!/usr/bin/env python


class AVR_Datagram(object):
	"""Do low-level datagram en/decoding for the H/K AVR protocol."""

	# Datagram "spec" for AVR->PC status updated
	AVR_PC_Status = (b"MPSEND", 3, 48)

	# Datagram "spec" for PC->AVR remote control commands
	PC_AVR_Command = (b"PCSEND", 2, 4)

	@staticmethod
	def calc_cksum(data):
		"""Return the two-byte checksum calculated from the given data.

		The checksum algorithm XORs the bytes at even/odd indices, and
		stores the result in the first/second byte of the return value.
		"""
		cksum = [0, 0]
		for i, b in enumerate(data):
			cksum[i % 2] ^= b
		return bytes(cksum)

	@staticmethod
	def full_dgram_len(dgram_spec):
		"""Return the total number of bytes in an AVR datagram
		following the given spec, including the protocol overhead.

		The datagram is structured as follows:
		 - Start keyword (== dgram_start), len(dgram_start) bytes
		 - Data type (== dgram_type), 1 byte
		 - Data length (== dgram_len), 1 byte
		 - Data, dgram_len bytes
		 - Checksum, 2 bytes
		"""
		dgram_start, dgram_type, dgram_len = dgram_spec
		return len(dgram_start) + 1 + 1 + dgram_len + 2

	@staticmethod
	def expect_dgram_start(dgram_spec):
		"""Return the bytes the we expect to occur at the start of an
                AVR datagram following the given spec.

		This consists of the start keyword, followed by the data type
                byte and the data length byte.
		"""
		dgram_start, dgram_type, dgram_len = dgram_spec
		return dgram_start + bytes([dgram_type, dgram_len])

	@classmethod
	def parse_dgram(cls, dgram, dgram_spec):
		"""Parse the given datagram, and return the data portion of it.

		The datagram is parsed according to the given spec, which is a
		(dgram_start, dgram_type, dgram_len) three-tuple specifying the
		expected datagram type and length (not including the 10-byte
		protocol overhead).

		Usually, this class handles status updates from the AVR side,
		in which case dgram_spec == ("MPSEND", 3, 48) makes sense.
		Otherwise, for parsing datagrams containing PC->AVR remote
		control commands, dgram_spec == ("PCSEND", 2, 4) makes sense.

		The datagram is structured as follows:
		 - 6 bytes:  Transmission keyword in ASCII (dgram_start)
		    - "MPSEND": AVR -> PC
		    - "PCSEND": PC -> AVR
		 - 1 byte:   Data Type (dgram_type)
		    - 0x01: DSP UPGRADE (PC -> AVR)
		    - 0x02: PC Remote controller (PC -> AVR)
		    - 0x03: Status data from AVR (AVR -> PC)
		    - 0x04: CPU UPGRADE (PC -> AVR)
		 - 1 byte:   Data Length (dgram_len)
		 - X bytes:  Data (X == dgram_len)
	         - 2 bytes:  Checksum:
	            - First byte: XOR of all even bytes in data
	            - Second byte: XOR of all odd bytes in data

		Consult the H/K AVR RS-232 protocol documentation for more
		details.
		"""
		dgram_start, dgram_type, dgram_len = dgram_spec
		full_dgram_len = cls.full_dgram_len(dgram_spec)

		assert isinstance(dgram, bytes)
		assert isinstance(dgram_start, bytes)
		assert len(dgram) == full_dgram_len, "Unexpected dgram length"
		assert dgram.startswith(dgram_start), "Unexpected start keyword"
		assert dgram[6] == dgram_type, "Unexpected type"
		assert dgram[7] == dgram_len, "Unexpected data length"
		data = dgram[8 : 8 + dgram_len]
		cksum = dgram[8 + dgram_len:]
		assert cksum == cls.calc_cksum(data), "Failed checksum"
		return data

	@classmethod
	def build_dgram(cls, data, dgram_spec):
		"""Embed the given data in a datagram of the given dgram_spec.

		Return the full datagram, including protocol overhead.
		"""
		dgram_start, dgram_type, dgram_len = dgram_spec
		assert isinstance(data, bytes)
		assert len(data) == dgram_len, "Incorrect data length"
		return dgram_start + bytes([dgram_type, dgram_len]) \
			+ data + cls.calc_cksum(data)
