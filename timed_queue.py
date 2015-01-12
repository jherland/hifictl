#!/usr/bin/env python

import sys
import time


class TimedQueue(object):
    """Encapsulate a queue of objects with associated timeouts.

    Each element in the queue consists of a (timeout, object) pair,
    sorted on timeout (some absolute time on the same format as
    returned from time.time()).

    Call current() to retrieve the object that is currently valid.
    This is the first object in the queue whose timeout has not yet
    expired. current() will automatically remove objects whose timeout
    has expired.

    Use add_absolute() and/or add_relative() to add objects with
    absolute/relative timeouts, respectively. Trying to add a timeout
    that has already expired will raise an AssertionError.

    At the "end" of the queue is a default object which will never
    expire. The default is given to the constructor, or to flush().
    """

    def __init__(self, default=None):
        self.q = [(sys.maxsize, default)]

    def current(self):
        """Return the currently active/available object.

        Discard all expired objects from the front of the queue.
        """
        now = time.time()

        # Remove all leading entries whose timeout < nw
        while self.q[0][0] < now:
            assert len(self.q)
            self.q.pop(0)

        # Return the first entry
        assert self.q[0][0] >= now
        return self.q[0][1]

    def add_absolute(self, timeout, obj):
        """Add an object with the given absolute timeout."""
        assert timeout > time.time()
        i = 0
        # Find appropriate place in self.q for the given obj
        while self.q[i][0] <= timeout:
            i += 1
        self.q.insert(i, (timeout, obj))

    def add_relative(self, rel_timeout, obj):
        """Add an object with a timeout relative to now."""
        return self.add_absolute(time.time() + rel_timeout, obj)

    def flush(self, default=None):
        """Empty the queue, and restart with a new default."""
        self.q = [(sys.maxsize, default)]


def main(args):
    now = time.time()

    q = TimedQueue("forever")
    q.add_relative(0.01, "immediate")
    q.add_relative(0.1, "soon")
    q.add_absolute(now + 0.2, "in a while")

    time.sleep(0.05)
    assert q.current() == "soon"
    time.sleep(0.1)
    assert q.current() == "in a while"
    time.sleep(0.1)
    assert q.current() == "forever"

    q.flush("and a while")
    q.add_relative(0.1, "whenever")
    assert q.current() == "whenever"
    time.sleep(0.05)
    assert q.current() == "whenever"
    time.sleep(0.1)
    assert q.current() == "and a while"

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
