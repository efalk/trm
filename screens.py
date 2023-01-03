#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

import curses
import errno
import getopt
import os
import re
import signal
import string
import sys
import textwrap
import time

import emailaccount
import imap
from keycodes import *
from utils import writeLog

PY3 = sys.version_info[0] >= 3
if PY3:
    def fromUtf(s):
        return s
    def toUtf(s):
        return s
    def unicode(s):
        return s
else:
    def fromUtf(s):
        return s.decode("utf8", "replace")
    def toUtf(s):
        return s.encode("utf8", "replace")


class ShortMessage(object):
    """Displays a message until the user presses any key. Screen will
    be cleared after, caller will want to move on to the next screen."""
    def __init__(self, win, message):
        self.win = win
        self.message = message
    def display(self):
        self.win.clear()
        self.win.addstr(1,0,self.message)
        self.win.refresh()
    def wait(self):
        c = self.win.getch()
        self.win.clear()
        self.win.refresh()
        return c
    def displayAndWait(self):
        self.display()
        return self.wait()


SCROLL_THRESH = 5

class PagerScreen(object):
    """Displays text and a prompt. If the user selects 'h',
    displays help text. If the user enters a command, returns the keycode
    of that command. Any method that doesn't have a specific
    return value returns self, for chaining."""
    def __init__(self, win, text, prompt1, prompt2, helpText):
        writeLog("New PagerScreen, text:")
        self.win = win
        self.text = text
        self.prompt1 = prompt1
        self.prompt2 = prompt2
        self.helpText = helpText
        # String of commands. Commands "h \nnp<>^$q" are implied.
        self.offset = 0
        self.subwin = None
        self.formatted = None
        self.curspos = (0,0)

    def resize(self):
        hgt, wid = self.win.getmaxyx()

        # Allocate space for the 3 fields:
        self.topRegion = (0,1)            # Region of top prompt
        self.bottomRegion = (hgt-1, 1)    # Region at the bottom
        bl = self.bottomRegion[0]
        self.textRegion = (2, bl-3)

        # Create subwindow for options
        tl,tn = self.textRegion
        self.subwin = self.win.subwin(tn,wid, tl,0)
        self.subwin.scrollok(True)

        self.__reformat()
        return self

    def __reformat(self):
        hgt,wid = self.subwin.getmaxyx()
        wrapper = textwrap.TextWrapper(width=wid-1)
        self.formatted = []
        for line in self.text.split('\n'):
            self.formatted.extend(wrapper.wrap(line) if line else [''])

    def display(self):
        """Redisplay everything"""
        if not self.formatted:
            self.resize()
        win = self.win
        hgt, wid = win.getmaxyx()

        tl,tn = self.topRegion
        bl,bn = self.bottomRegion

        win.clear()

        win.addstr(tl,0, self.prompt1)

        self.displayText()

        win.addstr(bl,0, self.prompt2)
        self.curspos = curses.getsyx()
        win.refresh()
        return self

    def displayText(self):
        """Display the text subwindow"""
        tl,tn = self.textRegion
        self.subwin.clear()
        return self.displayTextRegion(self.offset, self.offset+tn-1)

    def displayTextRegion(self, start, end):
        """Display part of the text subwindow"""
        win = self.win
        subwin = self.subwin
        offset = self.offset
        tl,tn = self.textRegion

        end = min(end, len(self.formatted)-1, tn+offset-1)

        for i in xrange(start, end+1):
            subwin.addstr(i-offset,0, toUtf(self.formatted[i]))

        subwin.refresh()
        return self

    def refresh(self):
        """Tell curses to bring screen up to date."""
        self.win.refresh()
        return self

    def setText(self, text):
        """Replace text. Caller should call refresh() after."""
        self.text = text
        __reformat(self)
        if self.current >= len(self.formatted):
            self.current = max(0, len(self.formatted) - self.textRegion[1] + 1)
        self.displayText()
        return self

    def setTopPrompt(self, prompt):
        """Replace top prompt. Caller should call refresh() after."""
        self.prompt1 = prompt
        self.win.addstr(self.topRegion[0],0, prompt)
        return self

    def setBottomPrompt(self, prompt):
        """Replace bottom prompt. Caller should call refresh() after."""
        self.prompt2 = prompt
        self.win.addstr(self.bottomRegion[0],0, prompt)
        return self

    def getOffset(self): return self.offset

    def scrollTo(self, i):
        """Adjust offset to the given value, scrolling if needed.
        Returns True if offset changed, False otherwise (because already
        at the end of the range.)"""
        if i < 0 or i >= len(self.formatted) or i == self.offset:
            return False
        subwin = self.subwin
        offset = self.offset
        delta = i - offset
        tl,tn = self.textRegion
        # Less than SCROLL_THRESH lines change, scroll and just fill in the gaps
        if i < offset and i >= offset-SCROLL_THRESH:
            # scroll down
            subwin.scroll(delta)
            self.offset = i
            self.displayTextRegion(i, offset)
        elif i > offset and i < offset+SCROLL_THRESH:
            # scroll up
            subwin.scroll(delta)
            self.offset = i
            self.displayTextRegion(offset+tn-delta, i+tn-delta)
        else:
            # Beyond that, complete refresh
            self.offset = i
            self.displayText()
        self.win.refresh()
        return True

    def scrollBy(self, i):
        return self.scrollTo(self.offset+i)

    def pageUp(self):
        if self.offset <= 0:
            return False
        tl,tn = self.textRegion
        self.offset -= tn - 1
        if self.offset < 0: self.offset = 0
        self.displayText()
        self.win.refresh()
        return True

    def pageDown(self):
        tl,tn = self.textRegion
        offset = self.offset
        offset += tn - 1
        if offset >= len(self.formatted):
            return False
        self.offset = offset
        self.displayText()
        self.win.refresh()
        return True

    def pageHome(self):
        return self.scrollTo(0)

    def pageEnd(self):
        return self.scrollTo(len(self.formatted) - self.textRegion[1] + 1)

    def commonKeys(self, c):
        """Handle common keys that scroll up and down. Return
        False if key was not handled by this method."""
        if c in (ord('\n'), ord('j'), CTRL_N, CTRL_E, curses.KEY_DOWN):
            self.scrollBy(1)
            return True
        if c in (ord('k'), CTRL_P, CTRL_Y, curses.KEY_UP):
            self.scrollBy(-1)
            return True
        if c in (ord('>'), CTRL_F, curses.KEY_NPAGE, ord(' ')):
            self.pageDown()
            return True
        if c in (ord('<'), CTRL_B, curses.KEY_PPAGE):
            self.pageUp()
            return True
        if c in (ord('^'), curses.KEY_HOME):
            self.pageHome()
            return True
        if c in (ord('$'), curses.KEY_END):
            self.pageEnd()
            return True
        if c in (curses.KEY_RESIZE, CTRL_L):
            writeLog("Executing resize")
            self.resize()
            self.display()
            return True
        return False    # didn't use this key

    def wait(self):
        while True:
            c = self.win.getch()
            writeLog("Received key %d" % c)
            if self.commonKeys(c):
                continue
            elif c in (ord('q'), ESC):
                return c
    def displayAndWait(self):
        self.display()
        return self.wait()



class OptionScreen(PagerScreen):
    """Displays a list of options and a prompt. If the user selects 'h',
    displays help text. If the user enters a command, returns the keycode
    of that command. If the user selects an option, returns the numeric
    index into the list. Any method that doesn't have a specific
    return value returns self, for chaining."""
    optKeys = "abcdefgijklmorstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    def __init__(self, win, options, prompt1, prompt2, helpText,
                cmds, long_cmds=None):
        super(OptionScreen,self).__init__(win, None, prompt1, prompt2, helpText)
        self.options = options
        # String of commands. Commands "h \nnp<>^$q" are implied.
        self.cmds = cmds = cmds + "h \nnp<>^$q"
        self.long_cmds = long_cmds
        self.optKeys = "".join([c for c in self.optKeys if c not in cmds])
        self.current = 0
        self.maxopts = 0        # Max options that will fit on the screen

    def resize(self):
        hgt, wid = self.win.getmaxyx()

        # Allocate space for the 4 or 5 fields:
        self.topRegion = (0,1)            # Region of top prompt
        self.statusRegion = (hgt-2, 1)    # status messages go here
        self.bottomRegion = (hgt-1, 1)    # Region at the bottom
        if self.long_cmds:
            cn = len(self.long_cmds)
            cl = self.statusRegion[0] - 1 - cn
            self.cmdRegion = (cl,cn)
            self.optRegion = (2, cl-3)
        else:
            bl = self.bottomRegion[0]
            self.optRegion = (2, bl-3)

        # Create subwindow for options
        ol,on = self.optRegion
        self.subwin = self.win.subwin(on,wid, ol,0)
        self.maxopts = min(on, len(self.optKeys))
        return self

    def display(self):
        """Redisplay everything"""
        win = self.win
        long_cmds = self.long_cmds
        if long_cmds:
            nlong = len(long_cmds) if long_cmds else 0
        hgt, wid = win.getmaxyx()

        tl,tn = self.topRegion
        bl,bn = self.bottomRegion
        if long_cmds:
            cl,cn = self.cmdRegion

        win.clear()

        win.addstr(tl,0, self.prompt1)

        self.displayOpts()

        if long_cmds:
            for cmd in long_cmds:
                win.addstr(cl,1, cmd)
                cl += 1

        win.addstr(bl,0, self.prompt2)
        win.refresh()
        return self

    def displayOpts(self):
        """Display the options subwindow"""
        win = self.win
        subwin = self.subwin
        options = self.options
        offset = self.offset
        current = self.current
        optKeys = self.optKeys
        ol,on = self.optRegion
        hgt, wid = win.getmaxyx()

        subwin.clear()

        #writeLog("options: " + str(options))
        n = min(self.maxopts, len(options) - offset)
        for i in range(n):
            subwin.addstr(i,1, optKeys[i])
            subwin.addstr(i,3, str(options[i+offset])[:wid-4])
            if i+offset == current:
                subwin.addstr(i,0, '>')

        subwin.refresh()
        return self

    def setOptions(self, options):
        """Replace options. Caller should call refresh() after."""
        self.options = options
        if self.current >= len(options):
            self.scrollTo(len(options)-1)
        else:
            self.displayOpts()
        return self

    def setStatus(self, status):
        """Replace status area. Caller should call refresh() after."""
        cursor = curses.getsyx()
        self.win.addstr(self.statusRegion[0],0, status)
        self.win.clrtoeol()
        curses.setsyx(cursor[0],cursor[1])
        return self

    def getOffset(self): return self.offset

    def getCurrent(self): return self.current

    def moveTo(self, i):
        """Adjust index to the given value, scrolling if needed.
        Returns True if index changed, False otherwise (because already
        at the end of the range.)"""
        if i < 0 or i >= len(self.options):
            return False
        subwin = self.subwin
        current = self.current
        offset = self.offset
        if i >= offset and i < offset + self.maxopts:
            # just move the caret
            writeLog("just move")
            subwin.addstr(current-offset, 0, ' ')
            subwin.addstr(i-offset, 0, '>')
            subwin.refresh()
            self.current = i
            return True
        # TODO: Out of the window, but no more than 5 lines, we scroll
        # Beyond that, complete refresh
        if i > current:
            # Scroll down
            self.current = i
            #self.offset = i
            self.offset = i - self.maxopts + 1
            self.displayOpts()
        else:
            # Scroll up
            self.current = i
            self.offset = i
            #self.offset = i - self.maxopts + 1
            if self.offset < 0: self.offset = 0
            self.displayOpts()
        return True

    def moveBy(self, i):
        return self.moveTo(self.current+i)

    def pageUp(self):
        if self.offset <= 0:
            return False
        self.offset -= self.maxopts - 1
        if self.offset < 0: self.offset = 0
        self.current = self.offset
        self.displayOpts()
        return True

    def pageDown(self):
        offset = self.offset
        offset += self.maxopts - 1
        if offset >= len(self.options):
            return False
        self.offset = offset
        self.current = offset
        self.displayOpts()
        return True

    def pageHome(self):
        return self.moveTo(0)

    def pageEnd(self):
        return self.moveTo(len(self.options) - 1)

    def commonKeys(self, c):
        """Handle common keys that scroll up and down. Return
        False if key was not handled by this method."""
        if c in (ord('n'), ord(']'), CTRL_N, curses.KEY_DOWN):
            self.moveBy(1)
            return True
        if c in (ord('p'), ord('['), CTRL_P, curses.KEY_UP):
            self.moveBy(-1)
            return True
        if c in (ord('>'), CTRL_F, curses.KEY_NPAGE, ord(' ')):
            self.pageDown()
            return True
        if c in (ord('<'), CTRL_B, curses.KEY_PPAGE):
            self.pageUp()
            return True
        if c in (ord('^'), curses.KEY_HOME):
            self.pageHome()
            return True
        if c in (ord('$'), curses.KEY_END):
            self.pageEnd()
            return True
        if c in (curses.KEY_RESIZE, CTRL_L):
            writeLog("Executing resize")
            self.resize()
            self.display()
            return True
        return False    # didn't use this key

    def isOptionKey(self, c):
        """If this character was one of the optKeys, determine which
        option it represented. Else return -1."""
        if c < 0 or c >= ord('z'):
            return -1
        c = chr(c)
        if c in "\n\r":
            return self.current
        idx = self.optKeys.find(c)
        if idx < 0:
            return idx
        if idx >= self.maxopts:
            return -1
        idx += self.offset
        if idx >= len(self.options):
            return -1
        return idx


class ColumnOptionScreen(OptionScreen):
    """Similar to OptionScreen, but displays multiple values in columns."""
    def __init__(self, win, options, prompt1, prompt2, helpText,
                cmds, long_cmds=None):
        super(ColumnOptionScreen,self).__init__(win, options, prompt1, prompt2, helpText,
                cmds, long_cmds)
        self.cwidths = []

    def resize(self):
        super(ColumnOptionScreen,self).resize()
        hgt, wid = self.win.getmaxyx()
        self.resizeColumns(wid)
        return self

    def resizeColumns(self, wid):
        """Meant to be subclassed."""
        self.cwidths = [(0,wid/2), (wid/2,wid/2)]
        return self

    def displayOpts(self):
        """Display the options subwindow"""
        win = self.win
        subwin = self.subwin
        options = self.options
        offset = self.offset
        current = self.current
        optKeys = self.optKeys
        ol,on = self.optRegion
        hgt, wid = win.getmaxyx()

        subwin.clear()

        n = min(self.maxopts, len(options) - offset)
        for i in range(n):
            subwin.addstr(i,1, optKeys[i])
            values = options[i+offset].getValues()
            cwidths = self.cwidths
            maxc = len(cwidths)
            subwin.move(i, 3)
            subwin.clrtoeol()
            for j,s in enumerate(values):
                if j < maxc and cwidths[j][1] > 0 and s:
                    subwin.addstr(i,3+cwidths[j][0], toUtf(s[:cwidths[j][1]]))
            if i+offset == current:
                subwin.addstr(i,0, '>')

        subwin.refresh()
        return self


class passwordWindow(object):
    """Tool to read password from user."""
    def __init__(self, parent, region=None):
        """Create password window as a sub-region of the parent window. If
        provided, region is (top,left, height, width). If not specified,
        region is centered in the parent window."""
        if not region:
            hgt, wid = parent.getmaxyx()
            region = (hgt//2-2, 1, 4, wid-2)
        self.win = parent.subwin(region[2],region[3], region[0], region[1])
    def display(self, prompt):
        self.win.clear()
        self.win.border()
        self.win.addstr(1,1, prompt)
        self.win.move(2,1)
        self.win.refresh()
    def read(self):
        writeLog("About to call getstr()")
        try:
            return self.win.getstr()
        except KeyboardInterrupt:
            writeLog("keyboard interrupt")
            return None
        finally:
            writeLog("finally")
            self.win.clear()
            self.win.refresh()
