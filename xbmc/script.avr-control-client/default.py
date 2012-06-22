"""
XBMC script for forwarding XBMC events to a AVR control server

Author: Johan Herland
"""

import sys

avr_fifo = "/tmp/avr_control"

cmd_map = {
	"VolumeUp":    "avr vol+",
	"VolumeDown":  "avr vol-",
	"Mute":        "avr mute",
	"HDMI1":       "hdmi 1",
	"HDMI2":       "hdmi 2",
	"HDMI3":       "hdmi 3",
	"HDMI4":       "hdmi 4",
#	"SurroundOn":  "surround ???",
}

assert len(sys.argv) > 0
args = sys.argv[1:]

if args and args[0] in cmd_map:
	if os.path.exists(avr_fifo):
#		print "Sending '%s' to %s" % (cmd_map[args[0]], avr_fifo)
		f = open(avr_fifo, "w")
		print >>f, cmd_map[args[0]]
		f.close()
	else:
		print "Cannot forward command '%s': %s does not exist" % (
			args[0], avr_fifo)
else:
	print "Unknown command '%s'" % (", ".join(args))
