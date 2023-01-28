#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import curses
import forms
import random
import sys
import screens
import time
import locale
locale.setlocale(locale.LC_ALL, '')

from utils import writeLog

SHORT_HELP = (("F1 ?  Help", "DEL delete 1 char", u"↑ BTAB Previous", "CR accept"),
              ("F2 ^G Guess", "^U  delete all", u"↓ TAB  Next", "ESC cancel"))

LOREM = """Sed ut perspiciatis, unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam eaque ipsa, quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt, explicabo. Nemo enim ipsam voluptatem, quia voluptas sit, aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos, qui ratione voluptatem sequi nesciunt, neque porro quisquam est, qui dolorem ipsum, quia dolor sit amet consectetur adipisci[ng] velit, sed quia non numquam [do] eius modi tempora inci[di]dunt, ut labore et dolore magnam aliquam quaerat voluptatem.
Ut enim ad minima veniam, quis nostrum[d] exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur? [D]Quis autem vel eum i[r]ure reprehenderit, qui in ea voluptate velit esse, quam nihil molestiae consequatur, vel illum, qui dolorem eum fugiat, quo voluptas nulla pariatur?

At vero eos et accusamus et iusto odio dignissimos ducimus, qui blanditiis praesentium voluptatum deleniti atque corrupti, quos dolores et quas molestias excepturi sint, obcaecati cupiditate non provident, similique sunt in culpa, qui officia deserunt mollitia animi, id est laborum et dolorum fuga.
Et harum quidem rerum facilis est et expedita distinctio. Nam libero tempore, cum soluta nobis est eligendi optio, cumque nihil impedit, quo minus id, quod maxime placeat, facere possimus, omnis voluptas assumenda est, omnis dolor repellendus.
Temporibus autem quibusdam et aut officiis debitis aut rerum necessitatibus saepe eveniet, ut et voluptates repudiandae sint et molestiae non recusandae. Itaque earum rerum hic tenetur a sapiente delectus, ut aut reiciendis voluptatibus maiores alias consequatur aut perferendis doloribus asperiores repellat."""

tracefile = open("./tracefile", "w")
callcount = 20


def main():
    try:
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)

        # Test 1, draw on raw stdscr
        dummytext = [u"This is line %d" % i for i in range(40)]
        for i in range(40):
            stdscr.addstr(i,0, dummytext[i])
        stdscr.refresh()
        key = forms.getUchar(stdscr)

        if False:
            # Test 2, display backgroundWin on top of stdscr
            #backgroundWin = stdscr.subwin(30,30,5,5)
            backgroundWin = curses.newwin(30,30,5,5)
            backgroundWin.refresh()
            key = forms.getUchar(stdscr)

            # Test 3, display add content to backgroundWin
            backgroundWin.clear()
            backgroundWin.border()
            backgroundWin.addstr(2,2, "this is backgroundWin")
            backgroundWin.move(4,4)
            backgroundWin.refresh()
            key = forms.getUchar(stdscr)

            # Test 4, redraw stdscr
            stdscr.touchwin()
            stdscr.refresh()
            key = forms.getUchar(stdscr)

            # Test 4, redraw backgroundWin
            backgroundWin.touchwin()
            backgroundWin.refresh()
            key = forms.getUchar(stdscr)

            # Test 5, add popupwin
            popupWin = curses.newwin(10,20, 30,7)
            popupWin.border()
            popupWin.addstr(1,1, "popup")
            popupWin.refresh()

            # Test 6, play with displaying windows
            while True:
                key = forms.getUchar(stdscr)
                if key == u's':
                    stdscr.refresh()
                elif key == 'b':
                    backgroundWin.refresh()
                elif key == 'p':
                    popupWin.refresh()
                elif key == u'S':
                    stdscr.touchwin()
                    stdscr.refresh()
                elif key == 'B':
                    backgroundWin.touchwin()
                    backgroundWin.refresh()
                elif key == 'P':
                    popupWin.touchwin()
                    popupWin.refresh()
                elif key == 'x':
                    backgroundWin = None
                elif key == 'q':
                    break

            return 0

        if False:
            # Same as above, but using subwin() instead of
            # newwin()
            # Test 2, display backgroundWin on top of stdscr
            backgroundWin = stdscr.subwin(30,30,5,5)
            backgroundWin.refresh()
            key = forms.getUchar(stdscr)

            # Test 3, display add content to backgroundWin
            backgroundWin.clear()
            backgroundWin.border()
            backgroundWin.addstr(2,2, "this is backgroundWin")
            backgroundWin.move(4,4)
            backgroundWin.refresh()
            key = forms.getUchar(stdscr)

            # Test 4, redraw stdscr
            stdscr.touchwin()
            stdscr.refresh()
            key = forms.getUchar(stdscr)

            # Test 4, redraw backgroundWin
            backgroundWin.touchwin()
            backgroundWin.refresh()
            key = forms.getUchar(stdscr)

            # Test 5, add popupwin
            popupWin = stdscr.subwin(10,20, 30,7)
            popupWin.border()
            popupWin.addstr(1,1, "popup")
            popupWin.refresh()

            # Test 6, play with displaying windows
            while True:
                key = forms.getUchar(stdscr)
                if key == u's':
                    stdscr.refresh()
                elif key == 'b':
                    backgroundWin.refresh()
                elif key == 'p':
                    popupWin.refresh()
                elif key == u'S':
                    stdscr.touchwin()
                    stdscr.refresh()
                elif key == 'B':
                    backgroundWin.touchwin()
                    backgroundWin.refresh()
                elif key == 'P':
                    popupWin.touchwin()
                    popupWin.refresh()
                elif key == 'x':
                    backgroundWin = None
                elif key == 'q':
                    break

            return 0

        theStatus = "The status"

        if False:
            # Test 7
            form = forms.Form(stdscr, True)
            label = form.Label(form, 1,-2, 1,1, "This is a label")
            text = form.Text(form, 1,30, 3,1)
            text2 = form.Text(form, 1,30, 5,1)
            text3 = form.Text(form, 1,30, 7,1)
            text3.setCallback(lambda w,t,_: label.set("text3: " + t).refresh(), None)
            form.setWidgets([label, text, text2, text3])
            form.win.clear()
            form.redraw().refresh()
            key = form.wait()

            # Test 8
    #        form = screens.ContentScreen(stdscr, dummytext, "ContentScreen", SHORT_HELP, theStatus)
    #        form.redraw().refresh()
    #        key = form.wait()

            # Test 9
    #        form = screens.ContentScreen(stdscr, dummytext, "AGAIN", SHORT_HELP, theStatus)
    #        form.redraw().refresh()
    #        key = form.wait()

            # Test 10 PagerScreen
            stdscr.clear()
            form = screens.PagerScreen(stdscr, dummytext, "PagerScreen", SHORT_HELP, theStatus)
            form.redraw().refresh()
            key = form.wait()

            # Test 11 TextPagerScreen
            stdscr.clear()
            form = screens.TextPagerScreen(stdscr, LOREM, "TextPagerScreen", SHORT_HELP, theStatus)
            form.redraw().refresh()
            key = form.wait()

            # Test 12 TextPagerScreen again (shorter text)
            stdscr.clear()
            form = screens.TextPagerScreen(stdscr, LOREM[:300], "Again", SHORT_HELP, theStatus)
            form.redraw().refresh()
            key = form.wait()

            # Test 13 ListScreen
            stdscr.clear()
            form = screens.ListScreen(stdscr, dummytext, "ListScreen", SHORT_HELP, theStatus)
            form.redraw().refresh()
            key = form.wait()

            # Test 14 OptionsScreen
            stdscr.clear()
            form = screens.OptionScreen(stdscr, dummytext, "OptionsScreen", SHORT_HELP, "q", theStatus)
            form.redraw().refresh()
            key = form.wait()

            # Test 15 TextPagerScreen again, long text
            stdscr.clear()
            form = screens.TextPagerScreen(stdscr, LOREM, "TextPagerScreen", SHORT_HELP, theStatus)
            form.redraw().refresh()
            key = form.wait()

        class ActiveItem(object):
            def __init__(self, s, active=None):
                self.s = s
                self._active = random.randint(0,1) if active == None else active
            def active(self):
                return self._active
            def __unicode__(self):
                return self.s
            def __str__(self):
                return self.s
        dummytext = [u"This is line %d self._active = random.randint(0,1) if active == None else active" % i for i in range(40)]
        activeList = [ActiveItem("start of list", False)]
        activeList.extend([ActiveItem(s) for s in dummytext])
        activeList.append(ActiveItem("end of list", False))

        stdscr.clear()
        form = screens.ActiveOptionScreen(stdscr, activeList, "ActiveOptionsScreen", SHORT_HELP, "q", theStatus)
        form.redraw().refresh()
        #key = form.wait()
        while True:
            key = form.getUchar()
            form.statusW.set("foo")
            form.statusW.win.refresh()
            if key == u'q':
                break
#            if form.handleKey(key) is not None:
#                form.setStatus("At row %d" % form.getCurrent())

        class ColumnItem(object):
            def __init__(self, values):
                self.values = values
            def getValues(self):
                return self.values
        lorem = LOREM.split()
        items = []
        while lorem:
            items.append(ColumnItem(lorem[:4]))
            del(lorem[:4])

        stdscr.clear()
        form = screens.ColumnOptionScreen(stdscr, items, "ColumnOptionsScreen", SHORT_HELP, "q", theStatus)
        form.redraw().refresh()
        while True:
            key = form.getUchar()
            if key == u'q':
                break
            if form.handleKey(key) is not None:
                form.setStatus("At row %d" % form.getCurrent())

        items = []
        for email in emails:
            items.append(ColumnItem(email))
        form = MessageOptionScreen(stdscr, items, "ColumnOptionsScreen", SHORT_HELP, "q", theStatus)
        form.redraw().refresh()
        while True:
            key = form.getUchar()
            if key == u'q':
                break
            if form.handleKey(key) is not None:
                form.setStatus("At row %d" % form.getCurrent())

    finally:
        curses.endwin()
    return 0

emails = [(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-04 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-06 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.local (Cron Daemon', u'2022-10-08 16:16', u'689'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.local (Cron Daemon', u'2022-10-09 16:16', u'689'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-11 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-13 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-14 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.local (Cron Daemon', u'2022-10-16 16:16', u'689'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-18 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-20 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-21 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-23 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-24 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-25 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-26 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-27 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-28 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-29 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-30 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-10-31 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.local (Cron Daemon', u'2022-11-01 16:16', u'689'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-04 16:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-06 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-08 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-10 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-11 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-13 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-15 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-16 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-18 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.local (Cron Daemon', u'2022-11-19 15:16', u'689'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-20 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-21 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-23 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-11-24 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.local (Cron Daemon', u'2022-11-25 15:16', u'689'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-12-01 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-12-02 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-12-03 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-12-04 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-12-05 15:17', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-12-06 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-12-07 15:16', u'731'),
	(u'U', u'Cron <falk@harrier> cd /Users/falk/Backups; /U', u'falk@harrier.localdomain (Cron', u'2022-12-09 15:16', u'731'),
	]

class MessageOptionsList(forms.Form.ColumnOptionsList):
    def resizeColumns(self):
        """Fill in the cwidths list with (column,width) pairs.
        Columns start at 0. Set width to 0 for any column to prevent
        it from being displayed. This default implementation gives
        the columns equal width."""
        ncol = len(self.content[0].getValues()) if self.content else 2
        wid = self.cwid - 3
        def setCwids(wids):
            self.cwidths = [(0,3)]
            col = 4
            for wid in wids:
                self.cwidths.append((col, wid))
                col += wid + 2
        if wid > 100:
            datewid = 16
            sizewid = 6
            wid -= 16+6
            wid -= 12            # column gaps
            subjwid = int(wid * 0.6)
            fromwid = wid - subjwid
            setCwids((subjwid, fromwid, datewid, sizewid))
        elif wid > 80:
            datewid = 16
            wid -= 16
            wid -= 10            # column gaps
            subjwid = int(wid * 0.6)
            fromwid = wid - subjwid
            setCwids((subjwid, fromwid, datewid))
        else:
            wid -= 8            # column gaps
            subjwid = int(wid * 0.6)
            fromwid = wid - subjwid
            setCwids((subjwid, fromwid))
        writeLog("wid=%d, cwidths=%s" % (self.cwid, self.cwidths))
        return self


class MessageOptionScreen(screens.ColumnOptionScreen):
    def _createContent(self):
        self.contentW = MessageOptionsList(self, self.contentHgt,-1,
                self.contentY,0, self.content, self.cmds)


if __name__ == '__main__':
    sys.exit(main())
