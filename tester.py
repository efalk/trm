#!/usr/bin/env python
# -*- coding: utf-8 -*-

import fcntl
import signal
import sys

import mbox
import filerange

def main():
    box = mbox.Mbox("Trash", "/Users/falk/Mail/AGevalia")
    print box.nmessages()
    nmessage = box.getOverview(myCallback)
    print nmessage
    print box.nmessages()
#    for i in range(20):
#        hdrs = box.getHeaders(i)
#        print "%d: %s" % (i, hdrs["X-UID"])
    m = box.getMessage(13)
    p = m.get_payload(0)
    s = p.get_payload()
    print type(s)
    u = s.decode("iso-8859-1")
    print type(u)
    for part in m.walk():
        if not part.is_multipart():
            print '---- PART ----'
            print part.get_param("charset")
            print part
    return 0

def myCallback(box, count, final, pct, message):
    print "%s: %d, %s, %d%% - %s" % (box, count, final, pct, message)

if __name__ == '__main__':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sys.exit(main())
