#!/usr/bin/env python2

import pty
import os
import fcntl
import termios
import time

from avr_conn import AVR_Connection
from avr_status import AVR_Status
from avr_command import AVR_Command


class StatusQueue(object):
	"""Encapsulate a queue of timed, future status messages."""

	def __init__(self, default):
		# Maintain a list of (timeout, status) pairs, sorted on timeout
		# The last element is a (None, default status) pair.
		self.q = [(None, default)]

	def add(self, timeout, status):
		assert timeout is not None
		i = 0
		# Find appropriate place in self.q for the given status
		while self.q[i][0] is not None and self.q[i][0] <= timeout:
			i += 1
		self.q.insert(i, (timeout, status))

	def current(self, now):
		"""Return the status appropriate for the given time.

		Discard all expired statuses from the queue.
		"""
		# Remove all leading entries whose timeout < nw
		while self.q[0][0] is not None and self.q[0][0] < now:
			assert len(self.q)
			del self.q[0]

		# Return the first entry
		assert self.q[0][0] is None or self.q[0][0] >= now
		return self.q[0][1]

	def flush(self, new_default):
		"""Empty the queue, and start anew with the given default."""
		self.q = [(None, new_default)]


class Fake_AVR(object):
	"""Impersonate an AVR unit.

	Receive remote commands, update internal state and provide plausible
	AVR_Status messages.
	"""

	CommonStatus = {
		"standby": AVR_Status(" " * 14, " " * 14, chr(0x00) * 14),
		"on": AVR_Status("FAKE AVR      ", "DOLBY DIGITAL ",
			"".join(map(chr, [0xc0, 0x00, 0x00, 0x00, 0xfd, 0xfb,
					  0x7a, 0x00, 0xc0] + [0x00] * 5))),
	}

	def __init__(self):
		self.start_time = time.time()

		self.standby = True
		self.cur_vol = -40

		self.status_queue = StatusQueue(self.CommonStatus["standby"])

	def status(self):
		"""Return AVR_Status diagram for current state."""
		return self.status_queue.current(time.time())

	def handle_command(self, cmd):
		now = time.time()
		print "(%fs) Received %s" % (now - self.start_time, cmd)
		if cmd.keyword == "POWER ON":
			assert self.standby
			self.standby = False
			self.status_queue.flush(self.CommonStatus["on"])
		elif cmd.keyword == "POWER OFF":
			assert not self.standby
			self.standby = True
			self.status_queue.flush(self.CommonStatus["standby"])


def main(args):
	master, slave = pty.openpty()
	print "You can now start ./avr_control.py -D %s" % (os.ttyname(slave))

	# Close the slave descriptor. It will be reopened by the client
	os.close(slave)

	# Make the master descriptor non-blocking.
	fl = fcntl.fcntl(master, fcntl.F_GETFL)
	fcntl.fcntl(master, fcntl.F_SETFL, fl | os.O_NONBLOCK)

	# Backup old term settings and setup new settings
	oldterm = termios.tcgetattr(master)
	newterm = termios.tcgetattr(master)
	newterm[3] = newterm[3] & ~termios.ECHO # lflags
	termios.tcsetattr(master, termios.TCSAFLUSH, newterm)

	# Repeatedly send status info every 5/100 seconds, until user aborts
	avr = Fake_AVR()
	recv_data = "" # Receive buffer
	recv_dgram_spec = ("PCSEND", 2, 4) # Receive PC->AVR remote commands
	send_dgram_spec = ("MPSEND", 3, 48) # Send AVR->PC status updates
	recv_dgram_len = AVR_Connection.full_dgram_len(recv_dgram_spec)
	try:
		while True:
			try:
				recv_data += os.read(master, 1024)
			except OSError as e:
				if e.errno not in [5, 11]:
					raise e
			while len(recv_data) >= recv_dgram_len:
				dgram = recv_data[:recv_dgram_len]
				recv_data = recv_data[recv_dgram_len:]
				avr.handle_command(AVR_Command.from_dgram(
					AVR_Connection.parse_dgram(
						dgram, recv_dgram_spec)))

			time.sleep(0.05)
			os.write(master, AVR_Connection.build_dgram(
				avr.status().dgram(), send_dgram_spec))
	except KeyboardInterrupt:
		pass

	# Close the remaining descriptor
	termios.tcsetattr(master, termios.TCSAFLUSH, oldterm)
	os.close(master)
	return 0


if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv[1:]))
