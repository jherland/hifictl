from dataclasses import dataclass


def decode_avr_text(text):
    return text.decode('ascii').replace('`', '\u2161')


def encode_avr_text(text):
    return text.replace('\u2161', '`').encode('ascii')


def surround_string(surround_set):
    """Return a string listing the given surround modes, separated by '+'."""
    return '+'.join(sorted(surround_set))


def surround_string_short(surround_set, limit=3):
    """Return a short string representing the given set of surround modes.

    Abbreviate each active surround mode in the given set to 2-4 char names,
    and return these separated by '+'. If more than limit are active, return
    '***' instead.
    """
    if len(surround_set) > limit:
        return '***'

    d = {  # Map long to short surround names.
        'DOLBY DIGITAL EX': 'DDEX',
        'DOLBY DIGITAL': 'DD',
        'DOLBY PRO LOGIC II': 'DPL2',
        'DOLBY PRO LOGIC': 'DPL',
        'DOLBY 3 STEREO': 'D3S',
        'STEREO': 'ST',
        'DOLBY HEADPHONE': 'DH',
        'DOLBY VIRTUAL': 'DV',
        'DTS ES': 'DTES',
        'DTS': 'DTS',
        'LOGIC 7': 'L7',
        'VMAX': 'VMAX',
        'DSP': 'DSP',
        '7CH.STEREO': '7CHS',
        '5CH.STEREO': '5CHS',
        'SURR.OFF': 'SROF',
    }
    return '+'.join(sorted([d[s] for s in surround_set]))


def channels_string(channels_set):
    """Return a string of the form X.Y from a set of input channels.

    Convert a set of input channels (as returned by .channels()) into a string
    like '2.0', '5.1' or '7.1'.
    """
    lfe = 1 if 'LFE' in channels_set else 0
    return f'{len(channels_set) - lfe}.{lfe}'


def speakers_string(speakers_set):
    """Return a string describing the speakers in the given set."""
    sets = [
        speakers_set & set(('L', 'R', 'l', 'r')),
        speakers_set & set(('C', 'c')),
        speakers_set & set(('LFE',)),
        speakers_set & set(('SL', 'SR', 'sl', 'sr')),
        speakers_set & set(('SBL', 'SBR', 'sbl', 'sbr')),
    ]
    return '/'.join(['+'.join(sorted(s)) for s in sets if s])


def speakers_string_short(speakers_set):
    """Return a short string of the form X.Y with the number of speakers."""
    lfe = 1 if 'LFE' in speakers_set else 0
    return f'{len(speakers_set) - lfe}.{lfe}'


@dataclass(frozen=True)
class AVR_Status:
    """Encapsulate a single AVR status update."""

    line1: str
    line2: str
    icons: bytes

    @classmethod
    def parse(cls, data):
        """Parse the data section of a status datagram from the AVR.

        The AVR continuously sends a 48 bytes of status info (wrapped in a
        datagram as parsed by avr_dgram) over the serial port. The data
        contains the same information that is visible on the AVR front display,
        and is structured as follows:
         - 16 bytes: VFD first line of characters:
            - 1 byte:   0xf0
            - 14 bytes: ASCII data (e.g. 'DVD           ')
            - 1 byte:   0x00
         - 16 bytes: VFD second line of characters:
            - 1 byte:   0xf1
            - 14 bytes: ASCII data (e.g. 'DOLBY DIGITAL ')
            - 1 byte:   0x00
         - 16 bytes: VFD icons encoded as a series of bit flags:
            - 1 byte:   0xf2
            - 14 bytes: VFD icons (see below comments for details)
            - 1 byte:   0x00

        Parse these 48 bytes, and return an object that contains these 3 data
        fields of the status report, or throw ValueError if parsing failed.
        """
        if len(data) != 48:
            raise ValueError(f'Unexpected length ({len(data)})')
        if not (
            data[0] == 0xF0
            and data[15] == 0x00
            and data[16] == 0xF1
            and data[31] == 0x00
            and data[32] == 0xF2
            and data[47] == 0x00
        ):
            raise ValueError(f'Malformed data ({data!r})')
        return cls(
            decode_avr_text(data[1:15]),
            decode_avr_text(data[17:31]),
            data[33:47],
        )

    def __str__(self):
        return '<AVR_Status: "{}" "{}" {}/{}/{} -> {}>'.format(
            self.line1,
            self.line2,
            self.source,
            channels_string(self.channels),
            surround_string(self.surround),
            speakers_string(self.speakers),
        )

    @property
    def data(self):
        """Re-create the raw AVR status data.

        Return a 48-byte data portion of an AVR datagram containing the
        information in this object.
        """
        assert len(self.line1) == 14
        assert len(self.line2) == 14
        assert len(self.icons) == 14
        return (
            bytes([0xF0])
            + encode_avr_text(self.line1)
            + bytes([0x00, 0xF1])
            + encode_avr_text(self.line2)
            + bytes([0x00, 0xF2])
            + self.icons
            + bytes([0x00])
        )

    @property
    def standby(self):
        """Return whether AVR is in standby mode."""
        # Assume we're  in standby if all self.icons is all 0x00
        return not any(self.icons)

    @property
    def muted(self):
        """Return whether AVR is in mute mode."""
        # when muted, the VFD flashes 'MUTE' at 1 Hz
        return self.line1.strip() in {'MUTE', ''} and self.line2.strip() == ''

    @property
    def volume(self):
        """Return current volume, or None if not currently visible."""
        line = self.line2.strip()
        if line.startswith('VOL ') and line.endswith('dB'):
            return int(line[4:7])
        return None

    @property
    def digital(self):
        """Return digital input gate, or None if not currently visible"""
        try:
            _, dig_str = self.line1.split('/')
        except ValueError:
            return None
        if dig_str.strip():
            return dig_str.strip()
        return None

    @property
    def surround(self):
        """Return the current surround mode.

        Returns the set of surround/processing modes enabled in this
        AVR status. The set contains zero of more of the following
        items:
         - 'DOLBY DIGITAL' or 'DOLBY DIGITAL EX'
         - 'DOLBY PRO LOGIC' or 'DOLBY PRO LOGIC II'
         - 'DOLBY 3 STEREO'
         - 'DOLBY HEADPHONE'
         - 'DOLBY VIRTUAL'
         - 'DTS' or 'DTS ES'
         - 'LOGIC 7'
         - 'VMAX'
         - 'DSP'
         - '5CH.STEREO' or '7CH.STEREO'
         - 'SURR.OFF'
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

        buf = self.icons[0:4]
        ret = set()
        if buf[0] & 0x20:
            ret.add('DOLBY DIGITAL EX')
        elif buf[0] & 0x40:
            ret.add('DOLBY DIGITAL')
        if buf[0] & 0x04:
            ret.add('DOLBY PRO LOGIC II')
        elif buf[0] & 0x08:
            ret.add('DOLBY PRO LOGIC')
        if buf[0] & 0x01:
            ret.add('DOLBY 3 STEREO')
        if buf[1] & 0x40:
            ret.add('STEREO')
        if buf[1] & 0x10:
            ret.add('DOLBY HEADPHONE')
        if buf[1] & 0x04:
            ret.add('DOLBY VIRTUAL')
        if buf[2] & 0x20:
            ret.add('DTS ES')
        elif buf[2] & 0x40:
            ret.add('DTS')
        if buf[2] & 0x08:
            ret.add('LOGIC 7')
        if buf[2] & 0x02:
            ret.add('VMAX')
        if buf[3] & 0x80:
            ret.add('DSP')
        if buf[3] & 0x10:
            ret.add('7CH.STEREO')
        elif buf[3] & 0x20:
            ret.add('5CH.STEREO')
        if buf[3] & 0x02:
            ret.add('SURR.OFF')
        return ret

    # The following lists the reverse-engineered interpretation of icons[4:8]
    # and how they correspond to the channel/speaker icons on the AVR display:
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

    @property
    def channels(self):
        """Return the channels present in the input signal.

        Returns the set of channels present in the input signal. The
        set contains zero of more of the following elements:
         - 'L'   - left channel
         - 'C'   - center channel
         - 'R'   - right channel
         - 'LFE' - low frequency effects (subwoofer)
         - 'SL'  - surround left
         - 'SR'  - surround right
         - 'SBL' - surround back left
         - 'SBR' - surround back right

        Typical return values:
         - A stereo input signal will yield a set containing L and R
         - A 5.1 surround signal will also contain C, LFE, SL and SR
         - A 7.1 surround signal will also contains SBL and SBR
        """
        buf = self.icons[4:8]
        ret = set()
        if buf[0] & 0x20:
            ret.add('L')  # left
        if buf[0] & 0x02:
            ret.add('C')  # center
        if buf[1] & 0x20:
            ret.add('R')  # right
        if buf[1] & 0x04:
            ret.add('LFE')  # low frequency effects (aka. sub-woofer)
        if buf[2] & 0x80:
            ret.add('SL')  # surround left
        if buf[2] & 0x04:
            ret.add('SR')  # surround right
        if buf[3] & 0x40:
            ret.add('SBL')  # surround back left
        if buf[3] & 0x02:
            ret.add('SBR')  # surround back right
        return ret

    @property
    def speakers(self):
        """Return the set of speakers used by the AVR.

        Returns a set listing the speakers that the AVR is currently
        using, as encoded in this AVR status message. The possible set
        members are:
         - 'L' or 'l':     A 'large' or 'small' left speaker
         - 'C' or 'c':     A 'large' or 'small' center speaker
         - 'R' or 'r':     A 'large' or 'small' right speaker
         - 'LFE':          A sub-woofer
         - 'SL' or 'sl':   A 'large' or 'small' surround left speaker
         - 'SR' or 'sr':   A 'large' or 'small' surround right speaker
         - 'SBL' or 'sbl': A 'large' or 'small' surr. back left speaker
         - 'SBR' or 'sbr': A 'large' or 'small' surr. back right speaker

        Note that the returned set is not necessarily equivalent to the
        speakers currently physically connected to the AVR. For example,
        with 5.1 speakers physically connected, it is still possible to
        manipulate the AVR into believing that there are 7.1 speakers
        (i.e. configuring the SBL/SBR speakers without actually
        connecting any). Conversely, when playing 2.0 material in
        'SURROUND OFF' mode, the set will not contain the surround
        speakers, although they are still physically connected.
        """
        buf = self.icons[4:8]
        ret = set()
        if buf[0] & 0x80:
            ret.add('L')
        elif buf[0] & 0x40:
            ret.add('l')
        if buf[0] & 0x08:
            ret.add('C')
        elif buf[0] & 0x04:
            ret.add('c')
        if buf[1] & 0x80:
            ret.add('R')
        elif buf[1] & 0x40:
            ret.add('r')
        if buf[1] & 0x08:
            ret.add('LFE')
        if buf[1] & 0x02:
            ret.add('SL')
        elif buf[1] & 0x01:
            ret.add('sl')
        if buf[2] & 0x10:
            ret.add('SR')
        elif buf[2] & 0x08:
            ret.add('sr')
        if buf[3] & 0x20:
            ret.add('SBL')
        elif buf[3] & 0x80:
            ret.add('sbl')
        if buf[3] & 0x01:
            ret.add('SBR')
        elif buf[3] & 0x04:
            ret.add('sbr')
        return ret

    @property
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

        Only one of these is active at any time, except when the AVR is
        off/standby, or while booting, in which case None is returned
        """
        # The following maps icons[8:12] to the corresponding source icon
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
        buf = self.icons[8:12]
        ret = set()
        if buf[0] & 0x30:
            ret.add('DVD')
        if buf[1] & 0xC0:
            ret.add('CD')
        if buf[2] & 0x60:
            ret.add('TAPE')
        if buf[2] & 0x06:
            ret.add('6CH')
        if buf[3] & 0x60:
            ret.add('8CH')
        if buf[0] & 0xC0:
            ret.add('VID1')
        if buf[0] & 0x03:
            ret.add('VID2')
        if buf[1] & 0x30:
            ret.add('VID3')
        if buf[1] & 0x01 and buf[2] & 0x80:
            ret.add('VID4')
        if buf[1] & 0x04:
            ret.add('FM')  # 0x0c (shares 0x08 with 'AM')
        if buf[1] & 0x02:
            ret.add('AM')  # 0x0a (shares 0x08 with 'FM')
        if len(ret) == 1:
            return ret.pop()
        else:
            return None
