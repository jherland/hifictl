#!/usr/bin/env python2

import serial
import time
import Queue


def calc_cksum(data):
	"""Return the two-byte checksum calculated from the given data.

	The checksum algorithm XORs the bytes at even/odd indices, and stores
	the result in the first/second byte of the result.
	"""
	cksum = [0, 0]
	for i, b in enumerate(data):
		cksum[i % 2] ^= ord(b)
	return chr(cksum[0]) + chr(cksum[1])


class AVR_Connection(object):
	"""Encapsulate the serial port connection to a Harman Kardon AVR."""

	Dgram_len = 58

	def __init__(self, serialport, baudrate = 38400):
		self.f = serial.Serial(serialport, baudrate)

		# It seems pyserial needs the rtscts flag toggled in
		# order to communicate consistently with the remote end.
		self.f.rtscts = True
		self.f.rtscts = False

		self.write_queue = Queue.Queue()

	def read_dgram(self):
		"""Block until exactly one 58-byte datagram has been received
		on the serial port. Return that datagram.
		"""
		while True:
			self.f.flush()
			dgram = self.f.read(self.Dgram_len)
			# All datagrams received from AVR starts with "MPSEND".
			i = dgram.find("MPSEND")
			if i == 0:
				return dgram
			elif i > 0:
				assert i < self.Dgram_len
				# read and return the rest of the dgram
				return dgram[i:] + self.f.read(i)

	def send_dgram(self, dgram):
		"""Send the given datagram to the AVR."""
		self.write_queue.put(dgram)

	def write_and_read(self):
		ret = self.read_dgram()
		if not self.write_queue.empty():
			dgram = self.write_queue.get()
			written = self.f.write(dgram)
			assert written == len(dgram)
			print "Wrote datagram '%s'" % (dgram) ### REMOVEME
		return ret

	def close(self):
		self.f.close()


class AVR_Status(object):
	"""Encapsulate a single AVR status update."""

	@staticmethod
	def parse_dgram(dgram):
		"""Parse a datagram containing status info from the AVR.

		The AVR continuously sends a 58-byte datagram over the serial
		port. The datagram contains the same information that is visible
		on the AVR front display. The datagram is structured as follows:

		 - 6 bytes:  Transmission, AVR -> PC: "MPSEND" (ASCII)
		 - 1 byte:   Data Type, AVR -> PC:    0x03
		 - 1 byte:   Data Length, 48 bytes:   0x30
		 - 48 bytes: Data:
		    - 16 bytes: VFD first line of characters:
		       - 1 byte:   0xf0
		       - 14 bytes: ASCII data (e.g. "HTPC")
		       - 1 byte:   0x00
		    - 16 bytes: VFD second line of characters:
		       - 1 byte:   0xf1
		       - 14 bytes: ASCII data (e.g. "DOLBY DIGITAL")
		       - 1 byte:   0x00
		    - 16 bytes: VFD first line of characters:
		       - 1 byte:   0xf2
		       - 14 bytes: B_VFD_icon (?)
		       - 1 byte:   0x00
		 - 2 bytes:  Checksum:
		    - High (second?) byte: XOR of all even bytes in data
		    - Low (first?) byte:   XOR of all odd bytes in data

		Return a 3-tuple containing the 3 data fields of the status
		report, or throw an exception if parsing failed.
		"""

		assert len(dgram) == 58, "Expected length 58, got %u" % (len(dgram))
		assert dgram.startswith("MPSEND")
		assert ord(dgram[6]) == 0x03
		assert ord(dgram[7]) == 0x30
		data = dgram[8:56]
		cksum = dgram[56:]
		calcsum = calc_cksum(data)
		assert cksum == calcsum, "Expected %02x %02x, got %02x %02x" % (ord(cksum[0]), ord(cksum[1]), ord(calcsum[0]), ord(calcsum[1]))
		assert ord(data[0]) == 0xf0
		assert ord(data[15]) == 0x00
		assert ord(data[16]) == 0xf1
		assert ord(data[31]) == 0x00
		assert ord(data[32]) == 0xf2
		assert ord(data[47]) == 0x00
		return (data[1:15], data[17:31], data[33:47])

	@classmethod
	def from_dgram(cls, dgram):
		return cls(*cls.parse_dgram(dgram))

	def __init__(self, line1, line2, icons):
		self.line1 = line1
		self.line2 = line2
		self.icons = icons

	def __str__(self):
		ret = "<AVR_Status: '%s' '%s' " % (self.line1, self.line2)
		for b in self.icons:
			ret += " %02x" % (ord(b))
		ret += ">"
		return ret

	def dgram(self):
		"""Create a datagram containing AVR status info.

		Return a 58-byte datagram containing the information in this
		object, with the encoding explained in the parse_dgram() docs.
		"""
		assert len(self.line1) == 14
		assert len(self.line2) == 14
		assert len(self.icons) == 14
		data = chr(0xf0) + self.line1 + chr(0x00) + \
		       chr(0xf1) + self.line2 + chr(0x00) + \
		       chr(0xf2) + self.icons + chr(0x00)
		cksum = calc_cksum(data)
		return "MPSEND" + chr(0x03) + chr(len(data)) + data + cksum


class AVR_Command(object):
	# The following dict is copied from the table on pages 10-11 in the
	# H/K AVR RS-232 interface document
	Commands = {
		"POWER ON":       (0x80, 0x70, 0xC0, 0x3F),
		"POWER OFF":      (0x80, 0x70, 0x9F, 0x60),
		"MUTE":           (0x80, 0x70, 0xC1, 0x3E),
		"AVR":            (0x82, 0x72, 0x35, 0xCA),
		"DVD":            (0x80, 0x70, 0xD0, 0x2F),
		"CD":             (0x80, 0x70, 0xC4, 0x3B),
		"TAPE":           (0x80, 0x70, 0xCC, 0x33),
		"VID1":           (0x80, 0x70, 0xCA, 0x35),
		"VID2":           (0x80, 0x70, 0xCB, 0x34),
		"VID3":           (0x80, 0x70, 0xCE, 0x31),
		"VID4":           (0x80, 0x70, 0xD1, 0x2E),
		"VID5":           (0x80, 0x70, 0xF0, 0x0F),
		"AM/FM":          (0x80, 0x70, 0x81, 0x7E),
		"6CH/8CH":        (0x82, 0x72, 0xDB, 0x24),
		"SLEEP":          (0x80, 0x70, 0xDB, 0x24),
		"SURR":           (0x82, 0x72, 0x58, 0xA7),
		"DOLBY":          (0x82, 0x72, 0x50, 0xAF),
		"DTS":            (0x82, 0x72, 0xA0, 0x5F),
		"DTS NEO:6":      (0x82, 0x72, 0xA1, 0x5E),
		"LOGIC7":         (0x82, 0x72, 0xA2, 0x5D),
		"STEREO":         (0x82, 0x72, 0x9B, 0x64),
		"TEST TONE":      (0x82, 0x72, 0x8C, 0x73),
		"NIGHT":          (0x82, 0x72, 0x96, 0x69),
		"1":              (0x80, 0x70, 0x87, 0x78),
		"2":              (0x80, 0x70, 0x88, 0x77),
		"3":              (0x80, 0x70, 0x89, 0x76),
		"4":              (0x80, 0x70, 0x8A, 0x75),
		"5":              (0x80, 0x70, 0x8B, 0x74),
		"6":              (0x80, 0x70, 0x8C, 0x73),
		"7":              (0x80, 0x70, 0x8D, 0x72),
		"8":              (0x80, 0x70, 0x8E, 0x71),
		"9":              (0x80, 0x70, 0x9D, 0x62),
		"0":              (0x80, 0x70, 0x9E, 0x61),
		"TUNE UP":        (0x80, 0x70, 0x84, 0x7B),
		"TUNE DOWN":      (0x80, 0x70, 0x85, 0x7A),
		"VOL UP":         (0x80, 0x70, 0xC7, 0x38),
		"VOL DOWN":       (0x80, 0x70, 0xC8, 0x37),
		"PRESET UP":      (0x82, 0x72, 0xD0, 0x2F),
		"PRESET DOWN":    (0x82, 0x72, 0xD1, 0x2E),
		"DIGITAL":        (0x82, 0x72, 0x54, 0xAB),
		"DIGITAL UP":     (0x82, 0x72, 0x57, 0xA8),
		"DIGITAL DOWN":   (0x82, 0x72, 0x56, 0xA9),
		"FMMODE":         (0x80, 0x70, 0x93, 0x6C),
		"DELAY":          (0x82, 0x72, 0x52, 0xAD),
		"DELAY UP":       (0x82, 0x72, 0x8A, 0x75),
		"DELAY DOWN":     (0x82, 0x72, 0x8B, 0x74),
		"COM SET":        (0x82, 0x72, 0x84, 0x7B),
		"COM UP":         (0x82, 0x72, 0x99, 0x66),
		"COM DOWN":       (0x82, 0x72, 0x9A, 0x65),
		"SPEAKER":        (0x82, 0x72, 0x53, 0xAC),
		"SPEAKER UP":     (0x82, 0x72, 0x8E, 0x71),
		"SPEAKER DOWN":   (0x82, 0x72, 0x8F, 0x70),
		"CHANNEL":        (0x82, 0x72, 0x5D, 0xA2),
		"RDS":            (0x82, 0x72, 0xDD, 0x22),
		"DIRECT":         (0x80, 0x70, 0x9B, 0x64),
		"CLEAR":          (0x82, 0x72, 0xD9, 0x26),
		"MEMORY":         (0x80, 0x70, 0x86, 0x79),
		"MULTIROOM":      (0x82, 0x72, 0xDF, 0x20),
		"MULTIROOM UP":   (0x82, 0x72, 0x5E, 0xA1),
		"MULTIROOM DOWN": (0x82, 0x72, 0x5F, 0xA0),
		"OSD":            (0x82, 0x72, 0x5C, 0xA3),
		"OSD LEFT":       (0x82, 0x72, 0xC1, 0x3E),
		"OSD RIGHT":      (0x82, 0x72, 0xC2, 0x3D),
		"SURR UP":        (0x82, 0x72, 0x85, 0x7A),
		"SURR DOWN":      (0x82, 0x72, 0x86, 0x79),
		"PRESCAN":        (0x80, 0x70, 0x96, 0x69),
		"DIMMER":         (0x80, 0x70, 0xDC, 0x23),
		"FAROUDJA":       (0x82, 0x72, 0xC6, 0x39),
		"TONE":           (0x82, 0x72, 0xC5, 0x3A),
	}

	@staticmethod
	def parse_dgram(dgram):
		"""Parse a datagram containing a command sent to the AVR.

		The AVR receives 14-byte datagram over the serial port
		containing remote control commands to be executed by the AVR.
		The datagram is structured as follows:

		 - 6 bytes:  Transmission, PC -> AVR: "PCSEND" (ASCII)
		 - 1 byte:   Data Type, Remote control command: 0x02
		 - 1 byte:   Data Length, 4 bytes: 0x04
		 - 4 bytes:  Remote control command from the above map.
		 - 2 bytes:  Checksum:
		    - High (second?) byte: XOR of all even bytes in data
		    - Low (first?) byte:   XOR of all odd bytes in data

		Return a 2-tuple containing 4-byte data value, and the
		corresponding keyword from the above map (or None). Throw an
		exception if parsing failed.
		"""

		assert len(dgram) == 14, "Expected length 14, got %u" % (len(dgram))
		assert dgram.startswith("PCSEND")
		assert ord(dgram[6]) == 0x02
		assert ord(dgram[7]) == 0x04
		data = dgram[8:12]
		cksum = dgram[12:]
		calcsum = calc_cksum(data)
		assert cksum == calcsum, "Expected %02x %02x, got %02x %02x" % (ord(cksum[0]), ord(cksum[1]), ord(calcsum[0]), ord(calcsum[1]))

		# Reverse-lookup the 4-byte data value in self.Commands
		keyword = None
		needle = [ord(c) for c in data]
		for k, v in self.Commands.iteritems():
			if needle == v:
				keyword = k
				break
		return (data, keyword)

	@classmethod
	def from_dgram(cls, dgram):
		data, keyword = cls.parse_dgram(dgram)
		return cls(keyword)

	def __init__(self, keyword):
		assert keyword in self.Commands
		self.keyword = keyword

	def __str__(self):
		return "<AVR_Command: '%s'>" % (self.keyword)

	def dgram(self):
		data = "".join(map(chr, self.Commands[self.keyword]))
		cksum = calc_cksum(data)
		return "PCSEND" + chr(0x02) + chr(len(data)) + data + cksum


def usage(msg):
	print msg + ":"
	print "Usage:"
	print "  avr_control.py <cmd>"
	print "  (where <cmd> is one of %s)" % (sorted(AVR_Commands.keys()))


def main(args):
	if len(args) >= 2 and args[0] == "-D":
		tty = args[1]
		args = args[2:]
	else:
		tty = "/dev/ttyUSB1"
	conn = AVR_Connection(tty)

	# Interpret command-line args as a single command to be sent to the AVR.
	if args:
		conn.send_dgram(AVR_Command(" ".join(args)).dgram())

	prev_dgram = None
	ts = time.time()
	while True:
		dgram = conn.write_and_read()
		if dgram == prev_dgram:
			continue # Skip if unchanged
		prev_dgram = dgram

		status = AVR_Status.from_dgram(dgram)

		now = time.time()
		print "%s (period: %f seconds)" % (status, now - ts)
		ts = now

	conn.close()
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))