#!/usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

import curses
import curses.ascii
import errno
import getopt
import os
import re
import signal
import string
import sys
import textwrap
import time

from utils import writeLog

CTRL_B = u'\002'
CTRL_E = u'\005'
CTRL_F = u'\006'
CTRL_L = u'\014'
CTRL_N = u'\016'
CTRL_P = u'\020'
CTRL_Y = u'\031'
KEY_TAB = u'\011'

SCROLL_THRESH = 5


#PY3 = sys.version_info[0] >= 3
#if PY3:
#    def fromUtf(s):
#        return s
#    def toUtf(s):
#        return s
#    unicode = str
#    basestring = str
#else:
#    def fromUtf(s):
#        return s.decode("utf8", "replace")
#    def toUtf(s):
#        # Only unicode (not str) needs encoding
#        if isinstance(s, unicode): return s.encode("utf8", "replace")
#        else: return s

PY3 = sys.version_info[0] >= 3
if PY3:
    def fromUtf(s):
        return s
    def toUtf(s):
        return s
    unicode = str
    basestring = str
else:
    def fromUtf(s):
        return s.decode("utf8", "replace")
    def toUtf(s):
        # Only unicode (not str) needs encoding
        if isinstance(s, unicode): return s.encode("utf8", "replace")
        else: return s



class Form(object):
    """Display a form for the user to fill out. Takes a list
    of Widget subclasses, displays them, and returns when one
    of the callbacks signals it. This is the framework that holds
    all of the widgets.

    Note: in these notes, "list" can usually mean anything that is
    iterable and indexible, e.g. a tuple. "string" can usually mean
    anything that returns a reasonable value for unicode() or str().

    Method "scrollTo()" sets the scroll amount of a widget and scrolls
    or redisplays as needed. "moveTo()" sets the currently-selected
    item in a list and scrolls if necessary to make it visible.
    Methods "setScroll()" and "setCurrent()" set the scroll and
    the currently-selected value, but take no other actions, so you'll
    want to call "redraw()" to completely redraw the widget.
    """

    class Widget(object):
        def __init__(self, form, hgt,wid, row,col):
            """Widget root class. Must be subclassed to be useful.
            @param hgt  height of widget
            @param wid  width of widget
            @param row  position of widget
            @param col

            row,col may be negative numbers, in which case they're
            taken relative to the bottom/right of the window.
            hgt,wid may be negative numbers, in which case they're
            taken as distances from the bottom/right of the window.
            Many widgets will allow you to specify hgt,wid as None,
            in which case they'll be computed from the widget contents."""
            self.form = form
            self.hgt = hgt
            self.wid = wid
            self.row = row
            self.col = col
            self.win = None
            self.chgt = hgt             # computed position and size
            self.cwid = wid
            self.crow = row
            self.ccol = col
            self.enabled = True
            self.focused = False
            self.resize()
        def _resizeCompute(self, hgt,wid, row,col):
            """Handle size changes. Recompute whatever needs computing."""
            fhgt = self.form.hgt
            fwid = self.form.wid
            self.crow = row if row >= 0 else fhgt + row
            self.ccol = col if col >= 0 else fwid + col
            self.chgt = hgt if hgt >= 1 else fhgt - self.crow + hgt
            self.cwid = wid if wid >= 1 else fwid - self.ccol + wid
            if self.crow + self.chgt > fhgt: self.chgt = fhgt - self.crow
            if self.ccol + self.cwid > fwid: self.cwid = fwid - self.ccol
            return self
        def resize(self):
            """Handle size changes. Recompute whatever needs
            computing. Allocate subwindow."""
            self._resizeCompute(self.hgt, self.wid, self.row, self.col)
            self.win = self.form.win.derwin(self.chgt,self.cwid, self.crow,self.ccol)
            self.win.clear()
            return self
        def setSize(self, hgt,wid, row=None,col=None):
            """Set the size and/or position of the widget. Set any value to
            None to leave it unchanged. Implicitly calls resize(). Caller should
            call redraw() and refresh() at some point."""
            writeLog("%s.setSize(%s,%s, %s,%s)" % (self, hgt,wid, row,col))
            if hgt is not None: self.hgt = hgt
            if wid is not None: self.wid = wid
            if row is not None: self.row = row
            if col is not None: self.col = col
            return self.resize()
        def set(self, value):
            """Set content."""
            return self
        def get(self):
            return None
        def clear(self):
            """Clear the subwindow, caller should call refresh(). Call
            this sparingly, as it can result in the entire screen being
            updated."""
            self.win.clear()
            return self
        def redraw(self):
            """Redraw the widget. Caller should call refresh() at some point"""
            return self
        def refresh(self):
            self.win.refresh()
            if not self.focused:
                self.form._replaceCursor()
            return self
        def enable(self, enabled=True):
            self.enabled = enabled
            return self.redraw()
        def handleKey(self, key):
            """Return None if not interested in this key. May return
            anything else if the key was used. Value may be meaningful
            to the application.  If the widget uses a callback, the
            value is likely to be the same one passed to the callback.
            Key may be an int keycode, or unicode character"""
            return None
        # Below this point are methods used for subclassing
        def canFocus(self):
            """Return False if don't want focus."""
            return False
        def takeFocus(self):
            """Notified that gained focus."""
            self.focused = True
            return self
        def loseFocus(self):
            """Notified that lost focus."""
            self.focused = False
            return self
        def placeCursor(self, row,col, win=None):
            """Place the cursor at the specific position."""
            if not win: win = self.win
            win.move(row,col)
            return self
        def _replaceCursor(self):
            """Put cursor back where it belongs. Does nothing for widgets
            that don't use the cursor."""
            return self

    class Label(Widget):
        def __init__(self, form, hgt,wid, row,col, label):
            self.label = label
            super(Form.Label,self).__init__(form, hgt,wid, row,col)
        def redraw(self):
            if self.chgt <= 0 or self.cwid <= 0: return self
            win = self.win
            # TODO: truncate line length correctly
            win.addnstr(0,0, toUtf(self.label), (self.cwid-1)*self.chgt)
            win.clrtoeol()
            return self
        def set(self, label):
            """Set contents of label. Caller should call refresh()"""
            self.label = label
            self.redraw()
            return self
        def get(self):
            return self.label
        def __repr__(self):
            return '<Label "%s">' % toUtf(self.label)

    class Text(Widget):
        """Present a one-line text field that the user can type into."""
        def __init__(self, form, hgt,wid, row,col, initial=u""):
            self.buffer = list(initial)
            super(Form.Text,self).__init__(form, hgt,wid, row,col)
            self.scroll = 0
            self.callback = self.client = None
        def resize(self):
            self._resizeCompute(self.hgt, self.wid, self.row, self.col)
            hgt = self.chgt
            wid = self.cwid
            self.win = win = self.form.win.derwin(hgt,wid, self.crow,self.ccol)
            if hgt < 3:
                self.textwin = self.win
                self.textwid = wid
            else:
                self.textwin = self.win.derwin(hgt-2, wid-2, 1,1)
                self.textwid = wid-2
            self.curspos = len(self.buffer)
        def set(self, s):
            """Set contents of text field. Caller should call refresh()"""
            self.buffer = list(s)
            self.scroll = 0
            self.curspos = len(self.buffer)
            self.redraw()
            return self
        def get(self):
            """Return current string value."""
            return u''.join(self.buffer)
        def setCallback(self, callback, client):
            self.callback = callback
            self.client = client
            return self
        def redraw(self):
            # If height is 3 or more, add a border
            if self.hgt >= 3:
                self.win.border()
            self.__draw()
            if self.focused:
                self._replaceCursor()
            else:
                self.form._replaceCursor()
            return self
        def canFocus(self):
            return True
        def takeFocus(self):
            self.focused = True
            curses.curs_set(1)
            self._replaceCursor()
            return self
        def loseFocus(self):
            self.focused = False
            return self
        def handleKey(self, key):
            """Edit text according to the key. Return None if the
            key was not used, else returns the key."""
            # I wish I could use getstr() for this, but I need to
            # end input on characters other than newline. Tab, backtab,
            # arrow keys, etc. all end input. Basically, only printing
            # characters are accepted. Also, under Python 2, there's no
            # way to receive unicode characters other than to decode them
            # manually.
            win = self.textwin
            if isinstance(key, int):      # Keycode
                return None            # At present, we're not interested in any of these
            else:
                #writeLog("character %#o" % ord(key))
                if printable(key):
                    #writeLog("printable: %c" % key)
                    wid = self.textwid
                    self.buffer.append(key)
                    l = len(self.buffer)
                    if l > wid-1: self.scroll = l - wid + 1
                    self.__draw()
                    self._replaceCursor()
                    win.refresh()
                    if self.callback:
                        self.callback(self, self.get(), self.client)
                    return key
                if key == u'\177':
                    #writeLog("del")
                    if self.buffer:
                        wid = self.textwid
                        del self.buffer[-1]
                        l = len(self.buffer)
                        if l >= wid-1: self.scroll = l - wid + 1
                        win.move(0,0)
                        win.clrtoeol()
                        #self.textwin.clear()
                        self.__draw()
                        win.refresh()
                        if self.callback:
                            self.callback(self, self.get(), self.client)
                    return key
                if key == "\25":
                    #writeLog("^U")
                    self.buffer = []
                    self.scroll = 0
                    #self.textwin.clear()
                    win.move(0,0)
                    win.clrtoeol()
                    self.__draw()
                    win.refresh()
                    if self.callback:
                        self.callback(self, self.get(), self.client)
                    return key
            return None
        def _replaceCursor(self):
            """Put the cursor where it belongs."""
            col = len(self.buffer) - self.scroll
            self.textwin.move(0,col)
            self.textwin.refresh()
            return self
        def __draw(self):
            b = u''.join(self.buffer[self.scroll:])
            wid = self.textwid - 1
            self.textwin.attrset(curses.A_UNDERLINE)
            self.textwin.addstr(0,0, " "*wid)
            self.textwin.addnstr(0,0, toUtf(b), wid)
        def __repr__(self):
            return '<Text "%s">' % toUtf(u"".join(self.buffer))

    class Button(Widget):
        """Button widget. Height should be 3 or more. Set width to 0
        to have it computed from the label. Set the callback to
        have something done when user activates (by pressing space)."""
        def __init__(self, form, hgt,wid, row,col, label):
            if not wid: wid = len(label) + 4
            super(Form.Button,self).__init__(form, hgt,wid, row,col)
            self.label = label
            self.activated = False
            self.callback = None
            self.client = None
        def setCallback(self, callback, client):
            self.callback = callback
            self.client = client
            return self
        def redraw(self):
            # If height is 3 or more, add a border
            if not self.enabled:
                self.win.attrset(curses.A_DIM)
            self.win.border()
            if not self.enabled:
                self.win.attrset(curses.A_DIM)
            elif self.activated:
                self.win.attrset(curses.A_STANDOUT)
            elif self.focused:
                self.win.attrset(curses.A_BOLD)
            self.win.addstr(self.hgt/2,1, '>' if self.focused else ' ')
            self.win.addnstr(self.hgt/2,2, toUtf(self.label), self.wid-4)
            self.win.addstr(self.hgt/2,self.wid-2, '<' if self.focused else ' ')
            self.win.attrset(curses.A_NORMAL)
            return self
        def activate(self, doCallback=True):
            """Called when button pressed."""
            self.activated = True
            self.redraw().refresh()
            if doCallback:
                if self.callback:
                    self.callback(self, self.client)
                else:
                    time.sleep(0.5)
            self.activated = False
            self.redraw().refresh()
            return self
        def canFocus(self):
            return True
        def takeFocus(self):
            curses.curs_set(0)
            self.focused = True
            self.redraw().refresh()
            return self
        def loseFocus(self):
            self.focused = False
            self.redraw().refresh()
            return self
        def handleKey(self, key):
            """key is either a unicode character, or an int keycode.
            Return True if pressed, else None"""
            if isinstance(key, int):
                return None            # At present, we're not interested in any of these
            else:
                if key == ' ':
                    if self.enabled:
                        self.activate()
                    return True
            return None
        def __repr__(self):
            return '<Button "%s">' % toUtf(self.label)

    class Checkbox(Button):
        """Checkbox widget. Set width to 0 to have it computed from
        the label. Set the callback to have something done when
        user activates (by pressing space). Obtain current state
        with getChecked()"""
        uncheckMark = "☐"
        checkMark = "✓"
        def __init__(self, form, hgt,wid, row,col, label):
            if not wid: wid = len(label) + 4
            super(Form.Checkbox,self).__init__(form, hgt,wid, row,col, label)
            self.checked = False
        def redraw(self):
            if not self.enabled:
                self.win.attrset(curses.A_DIM)
            elif self.activated:
                self.win.attrset(curses.A_STANDOUT)
            elif self.focused:
                self.win.attrset(curses.A_BOLD)
            self.win.addstr(self.hgt/2,0, '>' if self.focused else ' ')
            self.win.addnstr(self.hgt/2,1, toUtf(self.label), self.wid-4)
            self.win.addstr(self.hgt/2,self.wid-2, self.checkMark if self.checked else self.uncheckMark)
            #self.win.addstr(self.hgt/2,self.wid-2, '!' if self.checked else '.')
            self.win.attrset(curses.A_NORMAL)
            return self
        def get(self):
            return self.checked
        def set(self, checked):
            self.activate(checked, False)
            return self
        def activate(self, checked, doCallback=True):
            """Called when button pressed."""
            self.checked = checked
            self.activated = True
            self.redraw().refresh()
            if doCallback:
                if self.callback:
                    self.callback(self, self.client)
            self.activated = False
            self.redraw().refresh()
            return self
        def handleKey(self, key):
            """key is either a unicode character, or an int keycode. Return
            new state if pressed, else None"""
            if isinstance(key, int):
                return None            # At present, we're not interested in any of these
            else:
                if key == ' ':
                    if self.enabled:
                        self.activate(not self.checked)
                    return self.checked
            return None
        def __repr__(self):
            return '<Button "%s">' % toUtf(self.label)

    class ShortHelp(Widget):
        """Display an array of help prompts. Typically placed at
        the bottom of the form. Typically two lines high. Set any
        of hgt,wid, row,col to None to take the default values, which
        will place the widget at the bottom of the form, filling its
        width. Height to be determined by the first column of shortHelp.

        shortHelp is an array [rows][cols] of short help messages, e.g.
             (("F1 ?  Help", "DEL delete 1 char", u"↑ BTAB Previous", "CR accept"),
              ("F2 ^G Guess", "^U  delete all", u"↓ TAB  Next", "ESC cancel"))

        This widget does not respond to user input.  Disable to
        make invisible.
        """
        def __init__(self, form, hgt,wid, row,col, shortHelp):
            self.shortHelp = shortHelp
            writeLog("New ShortHelp(), len(help) = %d" % len(shortHelp))
            super(Form.ShortHelp,self).__init__(form, hgt,wid, row,col)
        def get(self):
            return self.shortHelp
        def set(self, shortHelp):
            self.shortHelp = shortHelp
            self.redraw()
        def redraw(self):
            """Display the short help at the bottom of the screen. Items
            that won't fit are discarded, so put the least important items
            at the end."""
            shortHelp = zip(*self.shortHelp)
            # Compute column widths
            wid = self.cwid
            colwids = map(max, [map(len, x) for x in shortHelp])
            colwid = sum(colwids)
            pad = max((wid - colwid) // (len(colwids)-1), 2)-1 if len(colwids) >= 2 else 0
            x = 0
            win = self.win
            if not self.enabled:
                win.attrset(curses.A_INVIS)
            for i,col in enumerate(shortHelp):
                cw = colwids[i]
                if x + cw >= wid:
                    break
                y = 0
                for s in col:
                    win.addstr(y,x, toUtf(s))
                    y += 1
                x += cw + pad
            if not self.enabled:
                win.attrset(curses.A_NORMAL)
            return self

    class OutputWindow(Widget):
        """Create a subwindow to which text can be sent. Also acts
        as a file-like object."""
        def __init__(self, form, hgt,wid, row,col, border=True):
            self.border = border
            super(Form.OutputWindow,self).__init__(form, hgt,wid, row,col)
        def resize(self):
            self._resizeCompute(self.hgt, self.wid, self.row, self.col)
            self.win = self.form.win.derwin(self.chgt,self.cwid, self.crow,self.ccol)
            if self.border:
                self.subwin = self.win.derwin(self.chgt-2,self.cwid-2, 1,1)
            else:
                self.subwin = self.win
            self.subwin.scrollok(True)
            return self
        def redraw(self):
            if self.border:
                self.win.border()
            return self
        def clear(self):
            """Clear the subwindow, caller should call refresh()"""
            self.subwin.clear()
            self.subwin.move(0,0)
            return self
        def write(self, s):
            self.subwin.addstr(toUtf(s))
            self.subwin.refresh()
            return self
        def writelines(self, lines):
            for line in lines:
                self.subwin.addstr(toUtf(line))
                self.subwin.addstr('\n')
            self.subwin.refresh()
            return self

    class Pager(Widget):
	"""Basic class that accepts a list of strings (or anything
	that can be treated as a string) and displays them one per
	line. The user can use the following keys to scroll through
	the list:
            \n j ^N ^E KEY_DOWN  -  scroll down one line
            k ^P ^Y KEY_UP - scroll up one line
            > ^F KEY_NPAGE - scroll down one page
            < ^B KEY_PPAGE - scroll up one page
            ^ KEY_HOME - scroll to top
            $ KEY_END - scroll to bottom

        All other keys are ignored and handleKey() returns None. Otherwise,
        returns the scroll amount (index of first displayed item in list.

        Items that will not fit in the width of the widget are truncated."""
        def __init__(self, form, hgt,wid, row,col, content):
            self.content = content
            self.contentLen = len(content)
            self.scroll = 0     # Amount window is scrolled
            self._direction = 1  # track the direction user is moving
            super(Form.Pager,self).__init__(form, hgt,wid, row,col)
        def resize(self):
            self._resizeCompute(self.hgt, self.wid, self.row, self.col)
            self.win = self.form.win.derwin(self.chgt,self.cwid, self.crow,self.ccol)
            self.win.scrollok(True)
            return self
        def set(self, content):
            """Replace content. Caller should call refresh() after."""
            self.content = content
            self.contentLen = len(content)
            if self.scroll >= self.contentLen:
                self.scroll = self.contentLen - 2
            self.win.clear()
            self.displayContent()
            return self
        def redraw(self):
            self.win.clear()
            self.displayContent()
            return self
        def displayContent(self, line0=0, line1=None):
            """Display the content within this range of lines."""
            if line1 is None: line1 = self.chgt - 1
            scroll = self.scroll
            win = self.win
            for i in xrange(line0, line1+1):
                if i+scroll >= self.contentLen:
                    break
                s = unicode(self.content[scroll+i])
                win.addstr(i,0, toUtf(s))
            return self
        def canFocus(self):
            return True
        def takeFocus(self):
            self.focused = True
            curses.curs_set(0)
            return self

        def getScroll(self):
            """Return the current scroll amount."""
            return self.scroll

        def getDirection(self):
            """Return the direction the user last moved the highlight."""
            return self._direction

        def scrollTo(self, i):
            """Adjust scroll to the given value."""
            if i < 0 or i >= self.contentLen or i == self.scroll:
                return self
            win = self.win
            scroll = self.scroll
            delta = i - scroll
            # Less than SCROLL_THRESH lines change, scroll and just fill in the gaps
            if i < scroll and i >= scroll-SCROLL_THRESH:
                # scroll down
                win.scroll(delta)
                self.scroll = i
                self.displayContent(0, -delta-1)
            elif i > scroll and i < scroll+SCROLL_THRESH:
                # scroll up
                win.scroll(delta)
                self.scroll = i
                self.displayContent(self.chgt - delta, self.chgt-1)
            else:
                # Beyond that, complete refresh
                self.scroll = i
                self.win.clear()
                self.displayContent()
            return self

        def scrollBy(self, i):
            return self.scrollTo(self.scroll+i)

        def pageUp(self):
            if self.scroll <= 0:
                return self
            self.scroll -= self.chgt - 1
            if self.scroll < 0: self.scroll = 0
            self.win.clear()
            self.displayContent()
            return self

        def pageDown(self):
            scroll = self.scroll
            scroll += self.chgt - 1
            if scroll >= self.contentLen:
                return self
            self.scroll = scroll
            self.win.clear()
            self.displayContent()
            return self

        def pageHome(self):
            return self.scrollTo(0)

        def pageEnd(self):
            return self.scrollTo(self.contentLen - self.chgt + 1)

        def handleKey(self, key):
            """Handle one character. Scroll if that's what's
            called for, return new scroll value if the key
            was used, else return None."""
            #writeLog("Pager.handleKey(%s)" % key)
            win = self.win
            if key in (u'\n', u'n', u'j', CTRL_N, CTRL_E, curses.KEY_DOWN):
                self.scrollBy(1).refresh()
                self._direction = 1
                return self.scroll
            if key in (u'p', u'k', CTRL_P, CTRL_Y, curses.KEY_UP):
                self.scrollBy(-1).refresh()
                self._direction = -1
                return self.scroll
            if key in ('>', CTRL_F, curses.KEY_NPAGE, u' '):
                self.pageDown().refresh()
                self._direction = 1
                return self.scroll
            if key in ('<', CTRL_B, curses.KEY_PPAGE):
                self.pageUp().refresh()
                self._direction = -1
                return self.scroll
            if key in ('^', curses.KEY_HOME):
                self.pageHome().refresh()
                self._direction = -1
                return self.scroll
            if key in ('$', curses.KEY_END):
                self.pageEnd().refresh()
                self._direction = 1
                return self.scroll
            return None    # didn't use this key

    class TextPager(Pager):
        """Similar to Pager except that long lines are wrapped as needed.
        If the content is a string instead of a list, it is broken on newlines.
        """
        def __init__(self, form, hgt,wid, row,col, text):
            self.rawtext = text
            writeLog("New TextPager()")
            super(Form.TextPager,self).__init__(form, hgt,wid, row,col, [])
            self.__reformat()
        def resize(self):
            super(Form.TextPager,self).resize()
            self.__reformat()
            return self
        def __reformat(self):
            wrapper = textwrap.TextWrapper(width=self.cwid-1)
            text = self.rawtext
            if isinstance(text, basestring):
                text = text.split('\n')
            self.content = []
            for line in text:
                self.content.extend(wrapper.wrap(line) if line else [''])
            self.contentLen = len(self.content)
        def set(self, text):
            """Replace text. Caller should call refresh() after."""
            self.rawtext = text
            self.__reformat()
            super(Form.TextPager,self).set(self.content)
            return self

    class List(Pager):
        """Like Pager, but adds the concept of a "current" item. Widget generally
        tries to keep that item on the screen. That item can be selected by the
        user by moving focus to it and hitting enter."""
        def __init__(self, form, hgt,wid, row,col, items):
            self.maxopts = 0    # max items that can be displayed
            self.current = 0
            super(Form.List,self).__init__(form, hgt,wid, row,col, items)
            self.callback = None
            self.client = None
            writeLog("New List, %d items" % len(self.content))
        def resize(self):
            super(Form.List,self).resize()
            self.maxopts = self.chgt
            return self
        def displayContent(self, line0=0, line1=None):
            """Display the items"""
            writeLog("List.displayContent(%d,%s)" % (line0,line1))
            if self.contentLen <= 0: return self
            if line1 is None:
                line1 = self.maxopts - 1
            elif line1 < line0:
                line0,line1 = line1,line0
            writeLog("List.displayContent(%d,%d)" % (line0, line1))
            win = self.win
            items = self.content
            scroll = self.scroll
            current = self.current
            wid = self.cwid
            #writeLog("items: " + str(items))
            limit = min(line1+1, self.contentLen - scroll)
            for i in xrange(line0, limit):
                if i+scroll == current:
                    win.attrset(curses.A_BOLD)
                win.addstr(i,0, '>' if i+scroll == current else ' ')
                win.addstr(i,1, toUtf(str(items[i+scroll])[:wid-2]))
                if i+scroll == current:
                    win.attrset(curses.A_NORMAL)
            return self
        def setCallback(self, callback, client):
            self.callback = callback
            self.client = client
            return self
        def getCurrent(self):
            """Get the index of the currently-selected item, or None."""
            return self.current if self.content else None
        def setCurrent(self, i, row=None):
            """Change the current item. Caller should call redraw() and refresh() after.
            This function simply sets the index of the current item. A full redraw
            is normally required. If you want to have the widget update itself visually
            and scroll as needed, then call moveTo() instead."""
            if row is not None:
                row = max(0, min(row, self.maxopts))
                self.scroll = max(0, i - row)
            else:
                # adjust the scroll only as needed
                if i < self.scroll:
                    self.scroll = i
                elif i >= self.scroll + self.maxopts:
                    self.scroll = i - self.maxopts + 1
            self.current = i
            return self
        def moveTo(self, i):
            """Change the current item, scroll as needed to keep it in the
            window."""
            if i is None: return self           # Do nothing
            current = self.current
            i = max(min(i, self.contentLen - 1), 0)
            #writeLog("List.moveTo(%d), current=%d, scroll=%d" % (i,current,self.scroll))
            if i == current:
                return self
            win = self.win
            scroll = self.scroll
            self.current = i
            self.displayContent(current-scroll, current-scroll)
            if i >= scroll and i < scroll + self.maxopts:
                # Didn't scroll, just redraw old and new entries
                #writeLog(" list didn't scroll, redraw lines %d, %d" % (current-scroll, i-scroll))
                self.displayContent(i-scroll, i-scroll)
            elif i < scroll:
                # Need to scroll up
                #writeLog(" list undraw line %d, scroll up scrollTo(%d)" % (current-scroll, i))
                self.scrollTo(i)
            else:
                # Need to scroll down
                #writeLog(" list undraw line %d, scroll down scrollTo(%d)" % (current-scroll, i-self.maxopts+1))
                self.scrollTo(i-self.maxopts+1)
            return self
        def moveBy(self, i):
            #writeLog("List.moveby(%d), call moveTo(%d)" % (i, self.current+i))
            return self.moveTo(self.current+i)
        def pageUp(self):
            #writeLog("List.pageUp(), current=%d, scroll=%d, call super.pageUp()" % \
            #    (self.current, self.scroll))
            super(Form.List,self).pageUp()
            self.current = self.scroll + self.maxopts - 1
            #writeLog(" set current = %d" % self.current)
            self.displayContent(self.current-self.scroll,self.current-self.scroll)
            return self
        def pageDown(self):
            #writeLog("List.pageDown(), current=%d, scroll=%d, call super.pageDown()" % \
            #    (self.current, self.scroll))
            super(Form.List,self).pageDown()
            self.current = self.scroll
            #writeLog(" set current = %d" % self.current)
            self.displayContent(self.current-self.scroll,self.current-self.scroll)
            return self
        def moveHome(self):
            #writeLog("List.moveHome(), current=%d, scroll=%d, call moveTo(0)" % (self.current, self.scroll))
            return self.moveTo(0)
        def moveEnd(self):
            return self.moveTo(self.contentLen-1)
        def handleKey(self, key):
            """Handle one keystroke. Scroll if that's what's
            called for, return new scroll value if the key
            was used, else return None."""
            #writeLog("List.handleKey(%s)" % keystr(key))
            if key in (u"\n", u"\r"):
                if self.callback:
                    self.callback(self, self.current, self.client)
                return self.current
            if key in (u'j', u'n', CTRL_N, CTRL_E, curses.KEY_DOWN):
                self.moveBy(1).refresh()
                return True
            if key in (u'k', u'p', CTRL_P, CTRL_Y, curses.KEY_UP):
                self.moveBy(-1).refresh()
                return True
            if key in ('>', CTRL_F, curses.KEY_NPAGE, u' '):
                self.pageDown().refresh()
                return True
            if key in ('<', CTRL_B, curses.KEY_PPAGE):
                self.pageUp().refresh()
                return True
            if key in ('^', curses.KEY_HOME):
                self.moveHome().refresh()
                return True
            if key in ('$', curses.KEY_END):
                self.moveEnd().refresh()
                return True
            return None    # didn't use this key

    class OptionsList(List):
        """Same as List, but items are indexed with a letter for quick
        selection. Caller provides a list of letters which are not available in
        'cmds'"""
        optKeys = "abcdefghijklmorstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        def __init__(self, form, hgt,wid, row,col, options, cmds):
            # String of commands. Commands "? \nnp<>^$q" are implied.
            self.cmds = cmds = cmds + "? np<>^$q"
            self.optKeys = "".join([c for c in self.optKeys if c not in cmds])
            super(Form.OptionsList,self).__init__(form, hgt,wid, row,col, options)
            writeLog("new OptionsList, %d items" % len(self.content))
        def resize(self):
            super(Form.OptionsList,self).resize()
            self.maxopts = min(len(self.optKeys), self.chgt)
            return self
        def displayContent(self, line0=0, line1=None):
            """Display the options"""
            if self.contentLen <= 0: return self
            if line1 is None:
                line1 = self.chgt - 1
            elif line1 < line0:
                line0,line1 = line1,line0
            win = self.win
            options = self.content
            scroll = self.scroll
            current = self.current
            optKeys = self.optKeys
            wid = self.cwid
            # Upper limit is the least of line1, options, maxopts
            limit = min(line1+1, self.contentLen - scroll, self.maxopts)
            for i in xrange(line0, limit):
                if i+scroll == self.current:
                    win.attrset(curses.A_BOLD)
                win.addstr(i,0, '>' if i+scroll == current else ' ')
                win.addstr(i,1, optKeys[i])
                win.addstr(i,3, toUtf(str(options[i+scroll])[:wid-4]))
                if i+scroll == current:
                    win.attrset(curses.A_NORMAL)
            return self
        def moveTo(self, i):
            """Change the current item, scroll as needed to keep it in the
            window. Caller should call refresh() after."""
            if i is None: return self           # Do nothing
            #writeLog("Options.moveto(%d)" % i)
            current = self.current
            i = max(min(i, self.contentLen - 1), 0)
            if i == current:
                return self
            win = self.win
            scroll = self.scroll
            self.current = i
            if i >= scroll and i < scroll + self.chgt:
                # Didn't scroll, just redraw old and new entries
                self.displayContent(current-scroll, current-scroll)
                self.displayContent(i-scroll, i-scroll)
            elif i < current:
                # No point in actually scrolling, the entire thing needs
                # a redraw.
                self.scroll = i
                self.win.clear()
                self.displayContent()
            else:
                self.scroll = i - self.chgt + 1
                self.win.clear()
                self.displayContent()
            return self
        def isOptionKey(self, key):
            """If this character was one of the optKeys, determine which
            option it represented. Else return None."""
            if not self.content:
                return None
            if isinstance(key, int):
                return None
            if key in u'\r\n':
                return self.current
            idx = self.optKeys.find(key)
            if idx < 0:
                return None
            if idx >= self.maxopts:
                return None
            idx += self.scroll
            if idx >= len(self.content):
                return None
            return idx
        def handleKey(self, key):
            rval = self.isOptionKey(key)
            if rval is not None:
                return rval
            return super(Form.OptionsList,self).handleKey(key)

    class ActiveOptionsList(OptionsList):
        """Same as OptionsList, but items must support the active() method which
        returns False if the item is not currently selectable."""
        def __init__(self, form, hgt,wid, row,col, items, cmds):
            super(Form.ActiveOptionsList,self).__init__(form, hgt,wid, row,col, items, cmds)
            self.current = self.nextActive(0)
        def displayContent(self, line0=0, line1=None):
            """Display the options"""
            if self.contentLen <= 0: return self
            if line1 is None:
                line1 = self.chgt - 1
            elif line1 < line0:
                line0,line1 = line1,line0
            win = self.win
            items = self.content
            scroll = self.scroll
            current = self.current
            optKeys = self.optKeys
            wid = self.cwid
            # Upper limit is the least of line1, items, maxopts
            limit = min(line1+1, self.maxopts, self.contentLen - scroll)
            for i in xrange(line0, limit):
                try:
                    active = items[i+scroll].active()
                except Exception as e:
                    writeLog("call option.active() failed with %s" % e)
                    active = False
                if i+scroll == self.current:
                    win.attrset(curses.A_BOLD)
                win.addstr(i,0, '>' if i+scroll == current else ' ')
                win.addstr(i,1, optKeys[i] if items[i+scroll].active() else ' ')
                win.addstr(i,3, toUtf(str(items[i+scroll])[:wid-4]))
                if i+scroll == current:
                    win.attrset(curses.A_NORMAL)
            return self
        def prevActive(self, i):
            """Return index of previous active object starting at i. If none,
            returns None."""
            if i < 0: return None
            if i >= self.contentLen: i = self.contentLen-1
            for j in range(i,-1,-1):
                if self.content[j].active():
                    return j
            return None
        def nextActive(self, i):
            """Return index of next active object starting at i. If none,
            returns None."""
            l = self.contentLen
            if i < 0: i = 0
            if i > l-1: return None
            for j in range(i,l):
                if self.content[j].active():
                    return j
            return None
        def moveBy(self, i):
            # A little tricky, since we only care about active items.
            if i < 0:
                return self.moveTo(self.prevActive(self.current+i))
            elif i > 0:
                return self.moveTo(self.nextActive(self.current+i))
            return self
        def movePageUp(self):
            return self.moveTo(self.nextActive(self.current-self.chgt+1))
        def movePageDown(self):
            return self.moveTo(self.prevActive(self.current+self.chgt-1))
        def moveHome(self):
            # We want to scroll to the top and then highlight the
            # first active item. But if that's not on the page, then
            # we'll have to scroll down enough to put it on the last line.
            old = self.current
            new = self.nextActive(0)
            scroll = max(0, new-self.chgt-1)
            if self.scroll == scroll:
                # No scroll, just change highlight
                self.current = new
                self.displayContent(old-scroll, old-scroll)
                self.displayContent(new-scroll, new-scroll)
            else:
                # Complete redraw
                self.scroll = scroll
                self.current = new
                self.win.clear()
                self.displayContent()
            return self
        def moveEnd(self):
            # New current item is last active item. If that's on
            # the screen, then great, just highlight it. Else
            # scroll to the end of the list. If that puts the new
            # item on the screen, we're good. Else scroll up to put
            # it at the top of the screen if possible.
            old = self.current
            new = self.prevActive(self.contentLen-1)
            scroll = self.scroll
            if new-scroll <= self.chgt-1:
                # Just shift highlight
                self.current = new
                self.displayContent(old-scroll, old-scroll)
                self.displayContent(new-scroll, new-scroll)
            else:
                # Can we scroll to end?
                scroll = self.contentLen - self.chgt + 1
                scroll = max(min(scroll, new), 0)
                self.scroll = scroll
                self.current = new
                self.win.clear()
                self.displayContent()
            return self


    class ColumnOptionsList(OptionsList):
	"""Same as OptionsList, but items must implement getValues()
	which returns a list of strings. By default, gives all
	columns equal width, but you can subclass this and override
	resizeColumns()."""
        def __init__(self, form, hgt,wid, row,col, items, cmds):
            self.cwidths = []
            super(Form.ColumnOptionsList,self).__init__(form, hgt,wid, row,col, items, cmds)
        def resize(self):
            super(Form.ColumnOptionsList,self).resize()
            self.resizeColumns()
            return self
        def resizeColumns(self):
            """Fill in the cwidths list with (column,width) pairs.
            Columns start at 0. Set width to 0 for any column to prevent
            it from being displayed. This default implementation gives
            the columns equal width."""
            ncol = len(self.content[0].getValues()) if self.content else 2
            wid = self.cwid
            wid = wid // ncol
            self.cwidths = [(i*wid,wid-1) for i in range(ncol)]
            return self
        def displayContent(self, line0=0, line1=None):
            """Display the options"""
            if self.contentLen <= 0: return self
            if line1 is None:
                line1 = self.chgt - 1
            elif line1 < line0:
                line0,line1 = line1,line0
            win = self.win
            items = self.content
            scroll = self.scroll
            current = self.current
            optKeys = self.optKeys
            wid = self.cwid
            cwidths = self.cwidths
            maxc = len(cwidths)
            # Upper limit is the least of line1, items, maxopts
            limit = min(line1+1, self.maxopts, self.contentLen - scroll)
            for i in xrange(line0, limit):
                if i+scroll == self.current:
                    win.attrset(curses.A_BOLD)
                win.addstr(i,0, '>' if i+scroll == current else ' ')
                win.addstr(i,1, optKeys[i])
                values = items[i+scroll].getValues()
                win.move(i, 3)
                win.clrtoeol()
                for j,s in enumerate(values):
                    if j < maxc and cwidths[j][1] > 0 and s:
                        win.addstr(i,3+cwidths[j][0], toUtf(s[:cwidths[j][1]]))
                if i+scroll == current:
                    win.attrset(curses.A_NORMAL)
            return self


    def __init__(self, win, border=True):
        """Create a new Form object.
        @param win     window in which the form will be displayed
        @param border  True to add a border around the form

        There are few layout utilities, clients are responsible for selecting
        the positions and sizes of the child widgets. Bad things will happen
        if you try to exceed the bounds of the window. Client must allow room
        for the border if there is one."""
        self.win = win
        self.border = border
        self.hgt, self.wid = win.getmaxyx()
        self.focus = None          # index into widgets of widget with focus
        self.widgets = []
        self.needResize = True
    def setWidgets(self, widgets):
        """Set the list of widgets. Caller should call redraw()
        and refresh() after."""
        self.widgets = widgets
        self.focus = self._searchFocus(0,1)
        return self
    def addWidgets(self, widgets):
        """Extend the list of widgets. Caller should call redraw()
        and refresh() after."""
        self.widgets.extend(widgets)
        return self
    def resize(self):
        """Call this after the size of the underlying window changes."""
        self.hgt, self.wid = self.win.getmaxyx()
        writeLog("Form.resize(), %dx%d" % (self.hgt, self.wid))
        if self.widgets:
            for widget in self.widgets:
                widget.resize()
        self.needResize = False
        return self
    def redraw(self):
        """Perform a complete redraw of this form, clearing the window
        first. Caller should call refresh()."""
        writeLog("%s redraw(), about to call clear" % self)
        self.win.clear()
        writeLog("Form.redraw(), needResize=%s" % self.needResize)
        if self.needResize: self.resize()
        if self.border:
            self.win.border()
        if self.widgets:
            for widget in self.widgets:
                #writeLog("call %s.redraw()" % widget)
                widget.redraw()
            if self.focus is not None:
                self.widgets[self.focus].takeFocus()
        self.win.refresh()
        return self
    def refresh(self):
        # The current focus widget gets drawn last so that its cursor
        # is placed correctly.
        fwidget = self.widgets[self.focus] if self.focus is not None else None
#       TODO: do we need to refresh them individually? It seems not.
#        for widget in self.widgets:
#            if widget != fwidget:
#                widget.refresh()
        self.win.refresh()
        # Refresh focus widget seperately so that the cursor
        # winds up where it belongs.
        if fwidget:
            fwidget.refresh()
        return self
    def _replaceCursor(self):
        """Put the cursor back where it belongs."""
        if self.focus is not None:
            self.widgets[self.focus]._replaceCursor()
    def getFocus(self):
        """Return the widget that currently has input focus, or None"""
        return self.widgets[self.focus] if self.focus is not None else None
    def setFocus(self, w):
        """Explicitly set the focus widget. w is a Widget or index."""
        f = self.focus
        if isinstance(w, Form.Widget):
            try:
                w = self.widgets.index(w)
            except:
                w = None
        if w == f:
            return self
        if f is not None:
            self.widgets[f].loseFocus()
        self.focus = w
        if w is not None:
            self.widgets[w].takeFocus()
        return self
    def nextFocus(self):
        """Advance focus"""
        w = self._searchFocus(self.focus+1 if self.focus is not None else 0, 1)
        self.setFocus(w)
        self.refresh()
        return self
    def previousFocus(self):
        """Move focus back"""
        w = self._searchFocus(self.focus-1 if self.focus is not None else 0, -1)
        self.setFocus(w)
        self.refresh()
        return self
    def _searchFocus(self, start, increment):
        """Starting with start, look for a widget that will accept
        focus. Return the index of that widget, or None. increment
        is +1 or -1"""
        n = len(self.widgets)
        start %= n
        for i in range(n):
            if self.widgets[start].canFocus():
                return start
            start = (start+increment) % n
        return None
    def getUchar(self):
        """Return either a unicode character of an integer keycode."""
        return getUchar(self.win)
    def handleKey(self, key):
        """Handle this key. Pass an int keycode or unicode character.
        returns None if not used, True if used directly,
        else whatever the widget returned."""
        writeLog("Form.handleKey(%s)" % keystr(key))
        if self.focus is not None:
            rval = self.widgets[self.focus].handleKey(key)
            if rval is not None:
                return rval
        if key in (KEY_TAB, curses.KEY_DOWN):
            self.nextFocus()
            return True
        if key in (curses.KEY_BTAB, curses.KEY_UP):
            self.previousFocus()
            return True
        if key == CTRL_L:
            writeLog("  calling redraw, refresh")
            self.redraw()
            self.refresh()
            return True
        if key == curses.KEY_RESIZE:
            writeLog("  calling resize, redraw, refresh")
            self.resize().redraw().refresh()
            return True
        if isinstance(key, basestring):
            if key in ("\t\r\n"):
                self.nextFocus()
                return True
        writeLog("  return None")
        return None    # didn't use this key
    def wait(self):
        """Process keystrokes until encounter one we don't want,
        then return it. This class is different from others: the
        return value will either be int for a keycode, or a unicode
        character. In practice you'll want to replace or override
        this function to handle input the way you want. For example,
        the default behavior of handleKey for CR is to move focus to
        the next item, while you might want to assign it a different
        meaning."""
        while True:
            key = getUchar(self.win)
            rval = self.handleKey(key)
            if rval is None:
                return key

def keystr(key):
    if isinstance(key, int): return "%#o" % key
    if not printable(key): return "%#o" % ord(key)
    return key


# Version-dependent utilities

if PY3:
    def getUchar(window):
        """Return one wide character or one keycode."""
        return window.get_wch()
    def printable(c):
        return s.isprintable()
else:
    def getUchar(window):
        """Return one unicode character or one int keycode.
        Only handles UTF-8."""
        # TODO: handle other encodings
        # TODO: timeout on malformed input
        ic = window.getch()
        if curses.ascii.isascii(ic):
            return unichr(ic)
        elif ic >= 0400:        # curses keycode
            return ic
        else:                   # Collect characters until decode() doesn't fail
            uchar_buffer = chr(ic)
            while True:
                ic = window.getch()
                if curses.ascii.isascii(ic):
                    # should not happen, abandon the buffer
                    return unichr(ic)
                elif ic >= 0400:
                    # should not happen, abandon the buffer
                    return ic
                else:
                    uchar_buffer += chr(ic)
                    try:
                        # TODO: preferred encoding
                        return uchar_buffer.decode('utf-8')
                    except UnicodeError as e:
                        if len(uchar_buffer) >= 4:
                            return u"?"
                        # otherwise, try with more characters

    def printable(c):
        # See https://en.wikipedia.org/wiki/Unicode_control_characters
        if c < ' ': return False
        if c <= '\176': return True  # most common case
        c = ord(c)
        for range in [ (0x007F,0x009F), (0x2000,0x200F), (0x2028,0x202F),
                       (0x205F,0x206F), (0x3000,0x3000), (0xFEFF,0xFEFF),]:
            if c >= range[0] and c <= range[1]:
                return False
        return True


