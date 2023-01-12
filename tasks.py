#!/usr/bin/env python
# -*- coding: utf8 -*-

"""Utilities to manage a limited threaded task queue."""

from __future__ import print_function

import errno
import os
import Queue
import signal
import sys
import threading
import time

from utils import writeLog

MAX_THREADS = 4

class Task(object):
    """Subclass and create one of these and call submit()
    to have it executed in the background. Call submit() from
    the app's main thread."""
    def run(self):
        """Override this."""
        # Optionally transmit status messages to _inqueue while
        # running.
        time.sleep(3)
    def submit(self):
        writeLog("this is submit")
        if not _threads or not _outqueue.empty() and len(_threads) < MAX_THREADS:
            writeLog("submit firing off a new thread")
            task = _TaskThread()
            _threads.append(task)
            task.setDaemon(True)
            task.start()
        writeLog("submit adding to queue")
        _outqueue.put(self)
        return self
    def sendInfo(self, obj):
        """Utility, send anything you want back to the main thread."""
        _inqueue.put(obj)
        return self

def checkForInfo():
    """Checks response queue to see if any task sent anything, and
    return one object. Returns None if no info currently available."""
    if _inqueue.empty():
        return None
    try:
        return _inqueue.get_nowait()
    except:
        return None


# Below this point is private

_outqueue = Queue.Queue()       # These names are from the POV of the client
_inqueue = Queue.Queue()
_threads = []

class _TaskThread(threading.Thread):
    def run(self):
        writeLog("This is _TaskThread.run()")
        while True:
            writeLog("_TaskThread waits for task")
            task = _outqueue.get()
            writeLog("_TaskThread receives new task")
            try:
                task.run()
            finally:
                writeLog("_TaskThread task complete")
                _outqueue.task_done()


# Unit test
if __name__ == '__main__':
  signal.signal(signal.SIGPIPE, signal.SIG_DFL)
  class ut(Task):
    def __init__(self, idx):
        self.idx = idx
    def run(self):
        print("This is task %d" % self.idx)
        time.sleep(self.idx%3 + 1)
        print("Task %d done" % self.idx)
  try:
    for i in xrange(20):
        task = ut(i)
        task.submit()
    _outqueue.join()
    time.sleep(2)
  except KeyboardInterrupt as e:
    print()
    sys.exit(1)

