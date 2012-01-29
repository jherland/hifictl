#!/usr/bin/env python2


class AVR_Status(object):
	"""Encapsulate a single AVR status update."""

	@staticmethod
	def parse_dgram(data):
		"""Parse a datagram containing status info from the AVR.

		The AVR continuously sends a 48-byte datagrams over the serial
		port. The datagram contains the same information that is visible
		on the AVR front display. The datagram is structured as follows
		(excluding the protocol overhead that is stripped by
		AVR_Connection):
		 - 16 bytes: VFD first line of characters:
		    - 1 byte:   0xf0
		    - 14 bytes: ASCII data (e.g. "DVD           ")
		    - 1 byte:   0x00
		 - 16 bytes: VFD second line of characters:
		    - 1 byte:   0xf1
		    - 14 bytes: ASCII data (e.g. "DOLBY DIGITAL ")
		    - 1 byte:   0x00
		 - 16 bytes: VFD icons encoded as a series of bit flags:
		    - 1 byte:   0xf2
		    - 14 bytes: VFD icons (see below comments for details)
		    - 1 byte:   0x00

		Return a 3-tuple containing the 3 data fields of the status
		report, or throw an exception if parsing failed.
		"""
		assert len(data) == 48, "Unexpected length"
		assert ord(data[0])  == 0xf0
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
		return "<AVR_Status: '%s' '%s' %s/%s/%s -> %s>" % (
			self.line1, self.line2, self.source(), self.ch_string(),
			self.surr_string(), self.spkr_string())

	def dgram(self):
		"""Create a datagram containing AVR status info.

		Return a 58-byte datagram containing the information in this
		object, with the encoding explained in the parse_dgram() docs.
		"""
		assert len(self.line1) == 14
		assert len(self.line2) == 14
		assert len(self.icons) == 14
		return chr(0xf0) + self.line1 + chr(0x00) + \
		       chr(0xf1) + self.line2 + chr(0x00) + \
		       chr(0xf2) + self.icons + chr(0x00)

	def surround(self):
		"""Decode and return the surround mode from AVR status.

		Returns the set of surround/processing modes enabled in this
		AVR status. The set contains zero of more of the following
		items:
		 - "DOLBY DIGITAL" or "DOLBY DIGITAL EX"
		 - "DOLBY PRO LOGIC" or "DOLBY PRO LOGIC II"
		 - "DOLBY 3 STEREO"
		 - "DOLBY HEADPHONE"
		 - "DOLBY VIRTUAL"
		 - "DTS" or "DTS ES"
		 - "LOGIC 7"
		 - "VMAX"
		 - "DSP"
		 - "5CH.STEREO" or "7CH.STEREO"
		 - "SURR.OFF"
		"""
		# The following lists the reverse-engineered interpretation of
		# icons[0:4] and how they correspond to the surround mode icons
		# on the AVR front display:
		#  DOLBY DIGITAL:               icons[0:4] == c0 00 00 00
		#  DOLBY PRO LOGIC II:          icons[0:4] == 1c 00 00 00
		#  DOLBY PRO LOGIC:             icons[0:4] == 18 00 00 00
		#  DOLBY VIRTUAL:               icons[0:4] == 00 0c 00 00
		#  DSP, SURR.OFF:               icons[0:4] == 00 00 01 86
		#  L7 LOGIC 7:                  icons[0:4] == 00 00 18 00
		#  SURR. OFF:                   icons[0:4] == 00 00 00 06
		#  DSP, 5 CH.STEREO:            icons[0:4] == 00 00 01 e8
		#  DTS:                         icons[0:4] == 00 00 c0 00
		#  DSP:                         icons[0:4] == 00 00 01 80
		#  DOLBY PLII, DOLBY HEADPHONE: icons[0:4] == 1c 30 00 00
		#  DOLBY DIGITAL, STEREO:       icons[0:4] == c0 40 00 00
		#  DOLBY DIGITAL EX:            icons[0:4] == e0 00 00 00
		#
		# icons[0:4]:
		#   [0]       [1]       [2]       [3]
		#   8421 8421 8421 8421 8421 8421 8421 8421
		#   ^^^^ ^^^^ ^^^^ ^^^^ ^^^^ ^^^^ ^^^^ ^^^^
		#   |||| |||| |||| |||| |||| |||| |||| |||?
		#   |||| |||| |||| |||| |||| |||| |||| ||* _SURR.OFF_
		#   |||| |||| |||| |||| |||| |||| |||| |** SURR.OFF
		#   |||| |||| |||| |||| |||| |||| |||| * 57_CH.STEREO_
		#   |||| |||| |||| |||| |||| |||| |||* 5_7_CH.STEREO
		#   |||| |||| |||| |||| |||| |||| ||* _5_7CH.STEREO
		#   |||| |||| |||| |||| |||| |||| |** 57CH.STEREO
		#   |||| |||| |||| |||| |||| |||| * _DSP_
		#   |||| |||| |||| |||| |||| |||** DSP
		#   |||| |||| |||| |||| |||| ||* _VMax_
		#   |||| |||| |||| |||| |||| |** VMax
		#   |||| |||| |||| |||| |||| * _L7 LOGIC 7_
		#   |||| |||| |||| |||| |||** L7 LOGIC 7
		#   |||| |||| |||| |||| ||* DTS _ES_ ?
		#   |||| |||| |||| |||| |* _DTS_ ES
		#   |||| |||| |||| |||| ** DTS ES
		#   |||| |||| |||| |||?
		#   |||| |||| |||| ||?
		#   |||| |||| |||| |* _DOLBY VIRTUAL_
		#   |||| |||| |||| ** DOLBY VIRTUAL
		#   |||| |||| |||* _DOLBY HEADPHONE_
		#   |||| |||| ||** DOLBY HEADPHONE
		#   |||| |||| |* DOLBY 3 _STEREO_
		#   |||| |||| * DOLBY _3_ STEREO ?
		#   |||| |||* _DOLBY_ 3 STEREO ?
		#   |||| ||** DOLBY 3 STEREO ?
		#   |||| |* DOLBY PRO LOGIC _II_
		#   |||| * _DOLBY PRO LOGIC_ II
		#   |||** DOLBY PRO LOGIC II
		#   ||* DOLBY DIGITAL _EX_
		#   |* _DOLBY DIGITAL_ EX
		#   ** DOLBY DIGITAL EX

		buf = tuple([ord(b) for b in self.icons[0:4]])
		ret = set()
		if   buf[0] & 0x20: ret.add("DOLBY DIGITAL EX")
		elif buf[0] & 0x40: ret.add("DOLBY DIGITAL")
		if   buf[0] & 0x04: ret.add("DOLBY PRO LOGIC II")
		elif buf[0] & 0x08: ret.add("DOLBY PRO LOGIC")
		if   buf[0] & 0x01: ret.add("DOLBY 3 STEREO")
		if   buf[1] & 0x40: ret.add("STEREO")
		if   buf[1] & 0x10: ret.add("DOLBY HEADPHONE")
		if   buf[1] & 0x04: ret.add("DOLBY VIRTUAL")
		if   buf[2] & 0x20: ret.add("DTS ES")
		elif buf[2] & 0x40: ret.add("DTS")
		if   buf[2] & 0x08: ret.add("LOGIC 7")
		if   buf[2] & 0x02: ret.add("VMAX")
		if   buf[3] & 0x80: ret.add("DSP")
		if   buf[3] & 0x10: ret.add("7CH.STEREO")
		elif buf[3] & 0x20: ret.add("5CH.STEREO")
		if   buf[3] & 0x02: ret.add("SURR.OFF")
		return ret

	def surr_string(self):
		return "+".join(sorted(self.surround()))

	# The following lists the reverse-engineered interpretation of
	# icons[4:8] and how they correspond to the channel/speaker icons
	# on the AVR front display:
	#
	#  - icons[4] & 0x80: L (large)
	#  - icons[4] & 0x40: L (small)
	#  - icons[4] & 0x20: L (signal)
	#  - icons[4] & 0x10: L (large) ?
	#  - icons[4] & 0x08: C (large)
	#  - icons[4] & 0x04: C (small)
	#  - icons[4] & 0x02: C (signal)
	#  - icons[4] & 0x01: C (large) ?
	#  - icons[5] & 0x80: R (large)
	#  - icons[5] & 0x40: R (small)
	#  - icons[5] & 0x20: R (signal)
	#  - icons[5] & 0x10: R (large) ?
	#  - icons[5] & 0x08: LFE (present)
	#  - icons[5] & 0x04: LFE (signal)
	#  - icons[5] & 0x02: SL (large)
	#  - icons[5] & 0x01: SL (small)
	#  - icons[6] & 0x80: SL (signal)
	#  - icons[6] & 0x40: SL (large) ?
	#  - icons[6] & 0x20: (listener icon?)
	#  - icons[6] & 0x10: SR (large)
	#  - icons[6] & 0x08: SR (small)
	#  - icons[6] & 0x04: SR (signal)
	#  - icons[6] & 0x02: SR (large) ?
	#  - icons[6] & 0x01: SBL (signal) ?
	#  - icons[7] & 0x80: SBL (small)
	#  - icons[7] & 0x40: SBL (signal)
	#  - icons[7] & 0x20: SBL (large)
	#  - icons[7] & 0x10: (line between SBL and SBR?)
	#  - icons[7] & 0x08: SBR (large)
	#  - icons[7] & 0x04: SBR (small)
	#  - icons[7] & 0x02: SBR (signal)
	#  - icons[7] & 0x01: SBR (large)

	def channels(self):
		"""Decode and return the channels present in the input signal.

		Returns the set of channels present in the input signal. The
		set contains zero of more of the following elements:
		 - "L"   - left channel
		 - "C"   - center channel
		 - "R"   - right channel
		 - "LFE" - low frequency effects (sub-woofer)
		 - "SL"  - surround left
		 - "SR"  - surround right
		 - "SBL" - surround back left
		 - "SBR" - surround back right

		Typical return values:
		 - A stereo input signal will yield a set containing L and R
		 - A 5.1 surround signal will also contain C, LFE, SL and SR
		 - A 7.1 surround signal will also contains SBL and SBR
		"""
		buf = [ord(b) for b in self.icons[4:8]]
		ret = set()
		if buf[0] & 0x20: ret.add("L") # left
		if buf[0] & 0x02: ret.add("C") # center
		if buf[1] & 0x20: ret.add("R") # right
		if buf[1] & 0x04: ret.add("LFE") # low freq. effects/sub-woofer
		if buf[2] & 0x80: ret.add("SL") # surround left
		if buf[2] & 0x04: ret.add("SR") # surround right
		if buf[3] & 0x40: ret.add("SBL") # surround back left
		if buf[3] & 0x02: ret.add("SBR") # surround back right
		return ret

	def ch_string(self):
		"""Return a string of the form X.Y denoting the input channels.

		This builds on top of self.channels(), and converts the returned
		set into a string typically like "2.0", "5.1" or "7.1".
		"""
		chs = self.channels()
		lfe = 0
		if "LFE" in chs:
			lfe = 1
		chs.discard("LFE")
		return "%u.%u" % (len(chs), lfe)

	def speakers(self):
		"""Decode and return the set of speakers used by to the AVR.

		Returns a set listing the speakers that the AVR is currently
		using, as encoded in this AVR status message. The possible set
		members are:
		 - "L" or "l":     A "large" or "small" left speaker
		 - "C" or "c":     A "large" or "small" center speaker
		 - "R" or "r":     A "large" or "small" right speaker
		 - "LFE":          A sub-woofer
		 - "SL" or "sl":   A "large" or "small" surround left speaker
		 - "SR" or "sr":   A "large" or "small" surround right speaker
		 - "SBL" or "sbl": A "large" or "small" surr. back left speaker
		 - "SBR" or "sbr": A "large" or "small" surr. back right speaker

		Note that the returned set is not necessarily equivalent to the
		speakers currently physically connected to the AVR. For example,
		with 5.1 speakers physically connected, it is still possible to
		manipulate the AVR into believing that there are 7.1 speakers
		(i.e. configuring the SBL/SBR speakers without actually
		connecting any). Conversely, when playing 2.0 material in
		"SURROUND OFF" mode, the set will not contain the surround
		speakers, although they are still physically connected.
		"""
		buf = [ord(b) for b in self.icons[4:8]]
		ret = set()
		if   buf[0] & 0x80: ret.add("L")
		elif buf[0] & 0x40: ret.add("l")
		if   buf[0] & 0x08: ret.add("C")
		elif buf[0] & 0x04: ret.add("c")
		if   buf[1] & 0x80: ret.add("R")
		elif buf[1] & 0x40: ret.add("r")
		if   buf[1] & 0x08: ret.add("LFE")
		if   buf[1] & 0x02: ret.add("SL")
		elif buf[1] & 0x01: ret.add("sl")
		if   buf[2] & 0x10: ret.add("SR")
		elif buf[2] & 0x08: ret.add("sr")
		if   buf[3] & 0x20: ret.add("SBL")
		elif buf[3] & 0x80: ret.add("sbl")
		if   buf[3] & 0x01: ret.add("SBR")
		elif buf[3] & 0x04: ret.add("sbr")
		return ret

	def spkr_string(self):
		"""Return a short string describing the speakers used by AVR."""
		spkrs = self.speakers()
		sets = [
			spkrs & set(("L", "R", "l", "r")),
			spkrs & set(("C", "c")),
			spkrs & set(("LFE",)),
			spkrs & set(("SL", "SR", "sl", "sr")),
			spkrs & set(("SBL", "SBR", "sbl", "sbr")),
		]
		return "/".join(["+".join(sorted(s)) for s in sets if s])

	def source(self):
		"""Decode and return the selected source from AVR status.

		The following sources may be returned:
		 - DVD
		 - CD
		 - TAPE
		 - 6CH
		 - 8CH
		 - VID1
		 - VID2
		 - VID3
		 - VID4
		 - FM
		 - AM

		Only one of these is active at any time, except when the AVR
		boots, in which case the string returned contains all of the
		above, separated with '+' signs.
		"""
		# The following lists the reverse-engineered interpretation of
		# icons[8:12] and how they correspond to the source icons
		# on the AVR front display:
		#  DVD:  icons[8:12] == 30 00 00 00
		#  CD:   icons[8:12] == 00 c0 00 00
		#  TAPE: icons[8:12] == 00 00 60 00
		#  6CH:  icons[8:12] == 00 00 06 00
		#  8CH:  icons[8:12] == 00 00 00 60
		#  VID1: icons[8:12] == c0 00 00 00
		#  VID2: icons[8:12] == 03 00 00 00
		#  VID3: icons[8:12] == 00 30 00 00
		#  VID4: icons[8:12] == 00 01 80 00
		#  FM:   icons[8:12] == 00 0c 00 00
		#  AM:   icons[8:12] == 00 0a 00 00
		buf = [ord(b) for b in self.icons[8:12]]
		ret = set()
		if buf[0] & 0x30: ret.add("DVD")
		if buf[1] & 0xc0: ret.add("CD")
		if buf[2] & 0x60: ret.add("TAPE")
		if buf[2] & 0x06: ret.add("6CH")
		if buf[3] & 0x60: ret.add("8CH")
		if buf[0] & 0xc0: ret.add("VID1")
		if buf[0] & 0x03: ret.add("VID2")
		if buf[1] & 0x30: ret.add("VID3")
		if buf[1] & 0x01 and buf[2] & 0x80: ret.add("VID4")
		if buf[1] & 0x04: ret.add("FM") # 0x0c (shares 0x80 with "AM")
		if buf[1] & 0x02: ret.add("AM") # 0x0a (shares 0x80 with "FM")
		if len(ret) == 0:
			return None
		elif len(ret) == 1:
			return ret.pop()
		else:
			return "+".join(sorted(ret))
