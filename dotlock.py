#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

from contextlib import contextmanager
import errno
import fcntl
import os
import signal
import socket
import sys
import time

PY3 = sys.version_info[0] >= 3
if PY3:
    basestring = str

@contextmanager
def doTimeout(seconds):
    """Creates a "with" context that times out after the
    specified time."""
    # TODO: move this to utilities?
    def timeout_handler(signum, frame):
        pass

    original_handler = signal.signal(signal.SIGALRM, timeout_handler)

    try:
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)

class __commonLock(object):
    def __init__(self):
        self.locked = False
    def check(self):
        """Return True if already locked. This isn't very useful,
        since the state of the lock could change immediately after
        this is called. Meant to be called before acquiring the lock."""
        return False
    def locked(self):
        """Return True if we hold the lock."""
        return self.locked

    def tryLock(self):
        """Acquire the lock, return True on success."""
        return False

    def lock(self, timeout=60):
        """Acquire the lock, wait up to timeout seconds. Return
        True on success."""
        if self.locked:
            return False
        if self.tryLock():
            return True
        dt = 1./16.     # first sleep, 1/16 second
        while timeout > 0:
            time.sleep(dt)
            timeout -= dt
            if self.tryLock():
                return True
            if dt < 8:
                dt = min(dt * 2, timeout)
        return False

    def unlock(self):
        """Release the lock. Implicitly called when the the lock goes
        out of scope."""
        pass

    def __enter__(self):
        return self
    def __exit__(self, exceptiontype, exception, traceback):
        self.unlock()
    def __del__(self):
        self.unlock()

    @staticmethod
    def unlink(file):
        """Same as os.unlink, but returns True/False instead of throwing."""
        try:
            os.unlink(file)
            return True
        except (OSError, IOError):
            return False


class DotLock(__commonLock):
    """Creates a dot-lock file for the file at the given path,
    and releases the lock when the object is freed. Best to use
    this in a "with" block. Does not support nested locking,
    so if called twice from the same thread, will return False
    immediately."""
    def __init__(self, path):
        super(DotLock,self).__init__()
        self.path = path
        self.cantlock = False
        self.lockfilename = path + ".lock"

    def tryLock(self):
        """Acquire the lock, return True on success."""
        # Because of NFS, this is a bit more complex than it ought to be.
        # From comments in mailx dotlock.c:
        # - make a mostly unique filename and try to create it.
        # - link the unique filename to our target
        # - get the link count of the target
        # - unlink the mostly unique filename
        # - if the link count was 2, then we are ok; else we've failed.
        if os.path.exists(self.lockfilename):
            return False
        host = socket.gethostname()
        pid = os.getpid()
        t = time.time()
        lockid = "%s %d %.3f" % (host, pid, t)
        tmpfilename = "%s.%s.%d.%.3f.lock" % (self.path, host, pid, t)

        try:
            with open(tmpfilename, "w") as ofile:
                print(lockid, file=ofile)
                print("locked by %s at %s" % (sys.argv[0], time.ctime(t)),
                    file = ofile)
        except (IOError,OSError) as e:
            if e.errno == errno.EACCES:
                # Nothing to do, just return success
                self.cantlock = True
                return True
            # Anything else is a real error
            raise

        try:
            os.link(tmpfilename, self.lockfilename)
        except (IOError,OSError) as e:
            self.unlink(tmpfilename)
            if e.errno == errno.EEXIST:
                return False
            raise

        try:
            st = os.stat(tmpfilename)
        except (IOError,OSError):
            return False
        finally:
            self.unlink(tmpfilename)

        self.locked = st.st_nlink == 2
        return self.locked

    def lock(self, timeout=60):
        """Acquire the lock, wait up to timeout seconds. Return
        True on success."""
        if self.locked:
            return False
        if self.tryLock():
            return True
        dt = 1./16.     # first sleep, 1/16 second
        while timeout > 0:
            time.sleep(dt)
            timeout -= dt
            if self.tryLock():
                return True
            if dt < 8:
                dt = min(dt * 2, timeout)
        return False

    def refresh(self):
        """Update the creation time on the lockfile so that other
        processes don't think it's become stale."""
        if not self.locked:
            return False
        with open(self.lockfilename, "a") as ofile:
            os.utime(self.lockfilename, None)
        return True

    def unlock(self):
        """Release the lock. Implicitly called when the the lock goes
        out of scope."""
        if self.locked:
            self.unlink(self.lockfilename)
            self.locked = False

    def __repr__(self):
        return "<dotlock %s>" % self.lockfilename


class FileLock(__commonLock):
    """Lock a file using fcntl. According to the Dovecot documentation,
    the Debian policies say to use fcntl and then dotlock, and that
    this policy probably applies to other operating systems too."""
    def __init__(self, file):
        super(FileLock,self).__init__()
        self.file = file

    def check(self):
        if self.locked:
            return True
        if self.tryLock():
            self.unlock()
            return True
        else:
            return False

    def tryLock(self):
        """Acquire the lock, return True on success."""
        if self.locked:
            return False
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except (OSError, IOError) as e:
            if e.errno in (errno.EACCES, errno.EAGAIN):
                return False
            raise
        self.locked = True
        return True

    def lock(self, timeout=None):
        if timeout is None:
            fcntl.flock(self.file, fcntl.LOCK_EX)
            self.locked = True
            return True
        else:
            with doTimeout(timeout):
                try:
                    fcntl.flock(self.file, fcntl.LOCK_EX)
                    self.locked = True
                    return True
                except (OSError, IOError) as e:
                    if e.errno == errno.EINTR:
                        return False
                    raise

    def unlock(self):
        """Release the lock. Implicitly called when the the lock goes
        out of scope."""
        if self.locked:
            fcntl.flock(self.file, fcntl.LOCK_UN)
            self.locked = False

    def __repr__(self):
        return "<filelock %d>" % self.file.fileno()


def testDotLock():
    print("locking")
#    with DotLock("./logfile") as lock:
    with DotLock("/var/mail/falk") as lock:
        print("lock: %s" % lock)
        ret = lock.lock(60)
        print("locked %s, sleeping" % ret)
        time.sleep(30 if ret else 3)
        print("refreshing lock")
        lock.refresh()
        time.sleep(30 if ret else 3)
        print("exit scope")
    print("sleeping")
    time.sleep(3)

def testFileLock():
    with open("./logfile","r") as logfile:
#    with open("/var/mail/falk","r") as logfile:
        with FileLock(logfile) as lock:
            print("lock: %s" % lock)
            ret = lock.lock(60)
            print("locked %s, sleeping" % ret)
            time.sleep(30 if ret else 3)
            print("about to unlock")
            time.sleep(1)
            print("exit scope")
        print("sleeping")
        time.sleep(3)

def main():
#    testFileLock()
    testDotLock()
    return 0


if __name__ == '__main__':
    sys.exit(main())
