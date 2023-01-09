#!/usr/bin/env python
# -*- coding: utf8 -*-

"""A file-like object that represents a range within another."""

from __future__ import print_function

import io
import os


class Filerange(io.IOBase):
    def __init__(self, basefile, start, size):
        self.basefile = basefile
        self.start = start
        self.size = size
        self.pos = 0            # relative to start
        basefile.seek(start)
    def read(self, size=-1):
        if self.pos >= self.size:
            return b""
        if size is None or size < 0:
            size = self.size - self.pos
        else:
            size = min(size, self.size - self.pos)
        rval = self.basefile.read(size)
        self.pos += len(rval)
        return rval
    def readline(self, size=-1):
        if self.pos >= self.size:
            return b""
        if size is None or size < 0:
            size = self.size - self.pos
        else:
            size = min(size, self.size - self.pos)
        rval = self.basefile.readline(size)
        self.pos += len(rval)
        return rval
    def seek(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self.basefile.seek(offset + self.start, whence)
            self.pos = offset
        elif whence == os.SEEK_CUR:
            self.basefile.seek(offset, whence)
            self.pos += offset
        else:   # SEEK_END
            self.pos = self.size + offset
            self.basefile.seek(self.pos + self.start, os.SEEK_SET)
    def tell(self):
        return self.pos
    def close(self):
        self.basefile.close()


