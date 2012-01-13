#!/usr/bin/env python2

import serial

serial_device = "/dev/ttyUSB1"
serial_baudrate = 38400

commands = {
        "on": (0x80, 0x70, 0xc0, 0x3f),
        "off": (0x80, 0x70, 0x9f, 0x60),
        "mute": (0x80, 0x70, 0xc1, 0x3e),
        # TODO: Add remaining commands from H/K PDF document
        "vol+": (0x80, 0x70, 0xc7, 0x38),
        "vol-": (0x80, 0x70, 0xc8, 0x37),
}

def calc_cksum(data):
        """Return the two-byte checksum calculated from the given data.

        The checsum algorithm XORs the bytes at even/odd indices, and stores
        the result in the first/second byte of the result.
        """
        cksum = [0, 0]
        for i, b in enumerate(data):
                cksum[i % 2] ^= ord(b)
        return chr(cksum[0]) + chr(cksum[1])

def send_command(ser, cmd):
        """Send the given command to the AVR.

        The given command must be a key in the commands dict.
        """
        data = "".join(map(chr, commands[cmd]))
        cmdstr = "PCSEND" + chr(0x02) + chr(0x04) + data + calc_cksum(data)
        written = ser.write(cmdstr)
        assert written == len(cmdstr)

def receive_status(ser):
        """Receive status info from the AVR.

        The AVR continuously sends a 58-byte datagram over the serial port.
        The datagram contains the same information that is visible on the AVR
        front display. The datagram is structured as follows:

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

        Return a 3-tuple containing the 3 data fields of the status report,
        or throw an exception if receiving/parsing failed.
        """

        # Read enough data to hold at least one complete datagram
        data = ser.read(58 * 3)
        # Assume that "MPSEND" only ever occurs at start of datagram
        i = data.index("MPSEND")
        dgram = data[i:i + 58]
        assert len(dgram) == 58, "Expected length 58, got %u" % (len(dgram))
        assert dgram.startswith("MPSEND")
        assert ord(dgram[6]) == 0x03
        assert ord(dgram[7]) == 0x30
        data = dgram[8:56]
        cksum = dgram[56:]
        calcsum = calc_cksum(data)
        assert cksum == calcsum, "Expected %02x %02x, got %02x %02x" % (
                ord(cksum[0]), ord(cksum[1]), ord(calcsum[0]), ord(calcsum[1]))
        assert ord(data[0]) == 0xf0
        assert ord(data[15]) == 0x00
        assert ord(data[16]) == 0xf1
        assert ord(data[31]) == 0x00
        assert ord(data[32]) == 0xf2
        assert ord(data[47]) == 0x00
        return (data[1:15], data[17:31], data[33:47])

def usage(msg):
	print msg + ":"
	print "Usage:"
	print "  avr_control.py <cmd>"
	print "  (where <cmd> is one of %s)" % (sorted(commands.keys()))

def main(args):
	# It seems pyserial needs the rtscts flag toggled in order to
	# communicate consistently with the remote end.
	ser = serial.Serial(serial_device, serial_baudrate, rtscts = True, timeout = 1)
	ser.rtscts = False

        # TODO: Turn this into a daemon that listens continuously on the serial
        # port for status datagrams, and updates an AVR_State instance.
        lines = receive_status(ser)
        print "Read status:"
        print "    '%s'" % (lines[0])
        print "    '%s'" % (lines[1])
        print "    '%s'" % (lines[2])
        print "   ",
        for b in lines[2]:
                print "%02x" % (ord(b)),
        print

        send_command(ser, "vol+")

        lines = receive_status(ser)
        print "Read status:"
        print "    '%s'" % (lines[0])
        print "    '%s'" % (lines[1])
        print "    '%s'" % (lines[2])
        print "   ",
        for b in lines[2]:
                print "%02x" % (ord(b)),
        print

        send_command(ser, "vol-")

        lines = receive_status(ser)
        print "Read status:"
        print "    '%s'" % (lines[0])
        print "    '%s'" % (lines[1])
        print "    '%s'" % (lines[2])
        print "   ",
        for b in lines[2]:
                print "%02x" % (ord(b)),
        print

        lines = receive_status(ser)
        print "Read status:"
        print "    '%s'" % (lines[0])
        print "    '%s'" % (lines[1])
        print "    '%s'" % (lines[2])
        print "   ",
        for b in lines[2]:
                print "%02x" % (ord(b)),
        print

        lines = receive_status(ser)
        print "Read status:"
        print "    '%s'" % (lines[0])
        print "    '%s'" % (lines[1])
        print "    '%s'" % (lines[2])
        print "   ",
        for b in lines[2]:
                print "%02x" % (ord(b)),
        print

        lines = receive_status(ser)
        print "Read status:"
        print "    '%s'" % (lines[0])
        print "    '%s'" % (lines[1])
        print "    '%s'" % (lines[2])
        print "   ",
        for b in lines[2]:
                print "%02x" % (ord(b)),
        print

	ser.close()
	return 0

if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
