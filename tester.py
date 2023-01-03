#!/usr/bin/env python
# -*- coding: utf-8 -*-

import fcntl
import signal
import sys

import mbox

def main():
    box = mbox.Mbox("Trash", "/Users/falk/Mail/Trash")
    print box.nmessages()
    nmessage = box.getOverview(myCallback)
    print nmessage
    print box.nmessages()
    return 0

def myCallback(box, count, final, pct, message):
    print "%s: %d, %s, %d%% - %s" % (box, count, final, pct, message)

if __name__ == '__main__':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sys.exit(main())
