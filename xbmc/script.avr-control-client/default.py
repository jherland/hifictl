"""
XBMC script for forwarding XBMC events to a AVR control server

Author: Johan Herland
"""

import sys

avr_fifo = "/tmp/avr_control"

cmd_map = {
	"VolumeUp":    "volume change +1",
	"VolumeDown":  "volume change -1",
	"Mute":        "mute toggle",
#	"HDMI1":       ???,
#	"HDMI2":       ???,
#	"HDMI3":       ???,
#	"HDMI4":       ???,
#	"SurroundOn":  "surround ???",
}

assert len(sys.argv) > 0
args = sys.argv[1:]

if args and args[0] in cmd_map:
#	print "Sending '%s' to %s" % (cmd_map[args[0]], avr_fifo)
	f = open(avr_fifo, "w")
	print >>f, cmd_map[args[0]]
	f.close()
else:
	print "Unknown command '%s'" % (", ".join(args))
