#!/usr/bin/env python2

import serial
import Queue


class AVR_Connection(object):
	"""Encapsulate the serial port communication to a Harman Kardon AVR."""

	@staticmethod
	def calc_cksum(data):
		"""Return the two-byte checksum calculated from the given data.

		The checksum algorithm XORs the bytes at even/odd indices, and
		stores the result in the first/second byte of the return value.
		"""
		cksum = [0, 0]
		for i, b in enumerate(data):
			cksum[i % 2] ^= ord(b)
		return chr(cksum[0]) + chr(cksum[1])

	@staticmethod
	def full_dgram_len(dgram_spec):
		"""Return the total number of bytes in aa AVR datagram
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

		assert len(dgram) == full_dgram_len, "Unexpected dgram length"
		assert dgram.startswith(dgram_start), "Unexpected start keyword"
		assert ord(dgram[6]) == dgram_type, "Unexpected type"
		assert ord(dgram[7]) == dgram_len, "Unexpected data length"
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
		assert len(data) == dgram_len, "Incorrect data length"
		return dgram_start + chr(dgram_type) + chr(dgram_len) \
			+ data + cls.calc_cksum(data)

	def __init__(self, serialport, baudrate = 38400):
		self.f = serial.Serial(serialport, baudrate)

		# It seems pyserial needs the rtscts flag toggled in
		# order to communicate consistently with the remote end.
		self.f.rtscts = True
		self.f.rtscts = False

		# Receive AVR->PC status info datagrams
		self.recv_dgram_spec = ("MPSEND", 3, 48)
		# Send PC->AVR remote control commands
		self.send_dgram_spec = ("PCSEND", 2, 4)

		self.write_queue = Queue.Queue()

	def recv_dgram(self, dgram_spec = None):
		"""Block until exactly one datagram of the given specification
		has been received on this AVR connection. Return the data
		portion of that datagram.
		"""
		if dgram_spec is None:
			dgram_spec = self.recv_dgram_spec
		full_dgram_len = self.full_dgram_len(dgram_spec)
		dgram = self.read_dgram(dgram_spec[0], full_dgram_len)
		return self.parse_dgram(dgram, dgram_spec)

	def read_dgram(self, dgram_start, dgram_len):
		"""Find the given start of the next datagram, and read the
		given number of bytes starting from there.

		Return the bytes read (== dgram_len).
		"""
		assert 1 <= len(dgram_start) < dgram_len
		self.f.flush()
		dgram = self.f.read(dgram_len)
		while True:
			i = dgram.find(dgram_start)
			if i == 0:
				# Datagram starts at beginning of dgram
				assert(len(dgram) == dgram_len)
				return dgram
			elif i > 0:
				# Datagram starts somewhere in the middle
				assert i < dgram_len
			else:
				# Start of datagram not (fully) found in dgram
				i = dgram_len + 1 - len(dgram_start)
			# Read the remainder of the datagram
			dgram = dgram[i:] + self.f.read(i)
			# Retry finding the start of the datagram

	def send_dgram(self, data, dgram_spec = None):
		"""Send the given data according to the given datagram spec."""
		if dgram_spec is None:
			dgram_spec = self.send_dgram_spec
		dgram = self.build_dgram(data, dgram_spec)
		self.write_queue.put(dgram)

	def write_and_recv(self):
		ret = self.recv_dgram()
		if not self.write_queue.empty():
			dgram = self.write_queue.get()
			written = self.f.write(dgram)
			assert written == len(dgram)
			print "Wrote datagram '%s'" % (" ".join(["%02x" % (ord(b)) for b in dgram])) ### REMOVEME
		return ret

	def close(self):
		self.f.close()
