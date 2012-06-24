"""
XBMC script for forwarding XBMC events to a A/V control server

Author: Johan Herland
"""

import sys

av_fifo = "/tmp/av_control"

assert len(sys.argv) == 2
av_cmd = sys.argv[1].strip()

if os.path.exists(av_fifo):
#	print "Sending '%s' to %s" % (av_cmd, av_fifo)
	f = open(av_fifo, "w")
	print >>f, av_cmd
	f.close()
else:
	print "Cannot forward '%s': %s does not exist" % (av_cmd, av_fifo)
