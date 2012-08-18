"""
XBMC script for forwarding XBMC events to a A/V control server

Author: Johan Herland
"""

import sys
import urllib

av_server = "http://sigma:8000/cmd/"

assert len(sys.argv) == 2
av_cmd = sys.argv[1].strip().split()
url = av_server + urllib.quote("/".join(av_cmd))

# print "Requesting", url
response = urllib.urlopen(url)
# print "Received HTTP status code %u" % (response.getcode())
# assert response.getcode() == 200
# print response.read()
