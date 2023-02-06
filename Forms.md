
# Forms module

The **Forms** module provides a basic widget-based interface on top
of Python curses. It works with both Python2 and Python3. With
Python3, it works better with Unicode characters since the Python3
version of curses handles Unicode.

The basic usage is to create a Form object on top of a curses window
(typically, but not necessarily, stdscr). Then create various Widget
objects attached to that Form. Pass the list of Widgets to
form.setWidgets() to complete the setup. Call form.redraw() and
form.refresh() to get everything on the screen.

Use form.getUchar() to read one keystroke from the user. This takes the
form of a unicode character or an integer keycode (e.g. curses.KEY\_UP).
Pass these keys to form.handleKey(). The form may use the keystroke for
its own purposes (e.g. TAB or KEY\_BTAB will shift focus to the next or
previous widget). In this case, the Form will return True to indicate that
the key was consumed.

Otherwise, the key is passed to whichever widget currently has focus.
That widget will return None to indicate that it wasn't interested in
the key, otherwise it will return a value that depends on the widget. The
Form will return whatever the widget returns.

In general, form.handleKey() returns None if the key was not used, or
anything else if it was.

There are no layout classes or container widgets. Client is
completely responsible for layout out the widgets within the form.

Most changes to any widget require calling `refresh()` to flush the
changes to the screen. When making multiple changes, you can wait
and call `form.refresh()` instead.

Any Form or Widget method that doesn't return a specific value returns
`self` instead. This allows chaining, e.g.
`label.setSize(3,20).redraw().refresh()`.

*Note*: in these notes, the term "list" can usually be replaced by
anything that is iterable and indexable. The term "string" can
usually be replaced by anything that returns a reasonable value
for `str()`.

----
# Example

This small code snippet

    # Initialize curses
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    # Create a form.
    form = forms.Form(stdscr, True)

    # Create some widgets
    label = form.Label(form, 1,-2, 1,1, "This is a label")
    text = form.Text(form, 1,30, 3,1)
    text2 = form.Text(form, 1,30, 5,1)

    # Put the widgets into the form. Create a couple more
    # widgets in-line while at it.
    form.setWidgets([label,
                     text,
                     text2,
                     form.Button(form, 3,None, 7,1, "The button"),
                     form.Checkbox(form, 1,None, 11,1, "The checkbox").set(True),
        ])
    form.redraw().refresh()
    key = form.wait()

Produces this screen

    ┌───────────────────────────────────────────────────┐
    │This is a label                                    │
    │                                                   │
    │ ______________________________                    │
    │                                                   │
    │ ______________________________                    │
    │                                                   │
    │┌────────────┐                                     │
    ││ The button │                                     │
    │└────────────┘                                     │
    │                                                   │
    │ The checkbox ✓                                    │
    │                                                   │
    │                                                   │
    │                                                   │
    │                                                   │
    │                                                   │
    └───────────────────────────────────────────────────┘

----
# Widgets

The base class for all widgets is the Form.Widget class. The methods
common to all widgets are as follows:

Some of these widgets may seem oddly eccentric. They were written to support
an app I was writing.

## Widget

Base class for all other widgets. Not normally instantiated directly.

### Constructor(form, hgt, wid, row, col)

All Widget constructors start with `(form, hgt, wid, row, col)`.
There may be additional arguments depending on the widget. Most common is the initial
value for the widget. 

#### Values for hgt, wid, row, col

Note that this module follows the curses convention of expressing coordinates as
row,column and height,width rather than x,y.

Note also that if the form has a border, you need to lay out your
widgets accordingly so as to not overwrite it.

**hgt** is the height of the widget. Non-negative integers specify
the height of the widget directly. Negative integers are taken as
distances from the bottom of the widget.  Thus, for example,
`Form.Widget(form, -3,40, 10,0)` would cause the widget to be placed
with the upper-left corner at row 10, column 0, and with a height
that brings it three rows from the bottom of the form.

In some cases, the value `None` may be used to have the Widget compute a height based
on its contents. Not all widgets support this.

**wid** is the width of the widget. The rules for non-negative and negative values
are the same as for **hgt**.

**row** is the location of the top of the widget. Negative values are taken relative
to the bottom of the form.

**col** is the location of the left edge of the widget. Negative values are taken
relative to the right edge of the form.

### set(value)

Set the widget's value. The type of the value depends on the widget. For example, it
would be a string for a Label widget, or a boolean for a Checkbox widget. The widget
will redraw itself. You should call `refresh()` after.

### get()

Return the widget's current value.

### setSize(hgt,wid, row=None,col=None)

Change the size and/or position of the widget. Any value may be None, meaning "no change".

Call `redraw()` or `form.redraw()` after calling this. And as usual, call `refresh()` or
`form.refresh()` as well.

### refresh()

Cause changes to be flushed to the terminal window. Call this (or `form.refresh()`)
after every change when it's time for the screen to be updated.

### enable(enabled=True))

Set the "enabled" state of a widget (True by default). The meaning
of "enabled" depends on the widget, but for interactive widgets,
being disabled usually causes them to stop accepting user input.

### handleKey(key)

Pass a keystroke (unicode character or integer keycode) to the widget.
If the widget isn't interested, it will return None. If the widget
consumed the keystroke but there's nothing else to report, it will
return True. The widget _may_ return another value depending on
its nature; for example a Checkbox will return True or False depending
on the new state of the checkbox.

### redraw()

Redraw the widget's content. You don't normally call this directly,
as it's called automatically when needed in most cases. Exceptions
include `setSize()` and `clear()`.

### resize()
Causes the widget to recompute its internal values after having its
size changed. You don't normally call this directly, as it's called
automatically by `setSize()` or by `form.resize()`.

### clear()

Clear the widget's window. Use this sparingly since it causes the entire
screen to be refreshed. Caller should call `redraw()` and `refresh()`.


## Label

This simply displays text on the screen and is non-interactive.

### Constructor:

    Form.Label(form, hgt,wid, row,col, label)

Creates a new label. 

### set(string)

Changes the content of the label. Caller should call `refresh()`


## Text

Text-entry field. Displays text on the screen which the user can edit. Editing
is relatively simple at present. Printable characters are appended to the
buffer. Delete key removes one character. ^U clears the field completely.

    imap server:  imap.example.com


### Constructor:

    Form.Text(form, hgt,wid, row,col, initial="")

If `hgt` is 3 or more, a border is added.

### setCallback(callback, client)

Sets a callback which will be called any time the text field is changed. The
callback is called as `callback(textwidget, value, client)`


## Button

Implements a "push button". This is the button label surrounded by a border.
The button is drawn in bold when it has the focus. Space key activates it.
When activated, the button's callback is called.

    ┌────────────────┐
    │**>Guess settings<**│
    └────────────────┘

Not very useful unless a callback is specified.

### Constructor:

    Form.Button(form, hgt,wid, row,col, label)

`hgt` should always be 3. Set `wid` to None to select a width wide enough
to accommodate the label.

### setCallback(callback, client)

Sets a callback which will be called any time the button is pressed. The
callback is called as `callback(buttonwidget, client)`

### activate(doCallback=True)

Activates the button as if the user had pressed it. `doCallback` should
always be True.


## Checkbox

Displays label text followed by ✓ or ☐. Space key toggles the value and
calls the callback if any.

    Use TLS (recommended) ✓

### Constructor:

    Form.Checkbox(form, hgt,wid, row,col, label)

### get()

Return True or False, depending on whether the checkbox is checked.

### set(checked)

Sets the checkbox status and calls the callback.

### activate(checked, doCallback=True)

Sets the checkbox status and calls the callback if doCallback is True

### handleKey(key)

If `key` is space, toggles the checkbox and calls the callback. Otherwise
does nothing and returns None.


## ShortHelp

Displays an array of short help texts, something like this:

    ?  Help      ↑ p Prev      PGUP < PrevPage    HOME ^ Top       + Add
    CR Select    ↓ n Next      PGDN > NextPage    END  $ Bottom    - Remove

Typically you would put a ShortHelp widget on the bottom two lines of
your app.

### Constructor:

    Form.ShortHelp(form, hgt,wid, row,col, shortHelp)

`shortHelp` is an array [rows][cols] of short help strings, e.g.

     (("F1 ?  Help", "DEL delete 1 char", u"↑ BTAB Previous", "CR accept"),
      ("F2 ^G Guess", "^U  delete all", u"↓ TAB  Next", "ESC cancel"))

Best practice is to set hgt to the number of lines of help, and wid to
-2 or -3, which will cause the help text to spread out across the width
of the form.


## OutputWindow

Creates a region in the form where text can be simply written. An OutputWindow
object is also a file-like object.

     ┌──────────────────────────────────────────────────────────────────────────────┐
     │Trying imap settings. This may take a while. ^C to cancel.                    │
     │Testing email address "alice@example.com"                                     │
     │Trying mail.example.com:993, ssl ... failed to connect                        │
     │Trying mail.example.com:143, no ssl ... failed to connect                     │
     │Trying imap.example.com:993, ssl ... failed to connect                        │
     │Trying imap.example.com:143, no ssl ... failed to connect                     │
     │Trying imap4.example.com:993, ssl ... failed to connect                       │
     │Trying imap4.example.com:143, no ssl ... failed to connect                    │
     │Trying example.com:993, ssl ...                                               │
     │                                                                              │
     │                                                                              │
     │                                                                              │
     │                                                                              │
     └──────────────────────────────────────────────────────────────────────────────┘

### Constructor:

    Form.OutputWindow(form, hgt,wid, row,col, border=True)

### write(string)

Write string to the output window. You'll usually want to end the string
with a newline, just as if writing to a terminal.

### writelines(lines)

Write a sequence of lines to the output window.


## Pager

Display a list of lines in a region of the form. Provides scrolling if
the list is longer than the height of the region.

Responds to keystrokes as follows:

    <newline>  j  ^N  ^E  KEY_DOWN     scroll down one line
    k  ^P  KEY_UP                      scroll up one line
    >  ^F  KEY_NPAGE                   scroll down one page
    <  ^B  KEY_PPAGE                   scroll up one page
    ^  KEY_HOME                        scroll to top
    $  KEY_END                         scroll to end

### Constructor:

    Form.Pager(form, hgt,wid, row,col, content)

`content` is an iterable of strings or string-like objects.

### getScroll()

Return the current scroll amount. E.g. returns 0 if scrolled to the top.

### getDirection()

Returns the direction the user last scrolled, +1 or -1.

### scrollTo(i)

Sets the scroll amount to `i`. User should call `refresh()` after calling this.

### scrollBy(i)

Adjust the scroll by the given amount.

### pageUp()

Scroll up one page

### pageDown()

Scroll down one page

### pageHome()

Scroll to top

### pageEnd()

Scroll to end


## TextPager

Similar to Pager, except that long lines are wrapped as needed. If `content`
is given as a single string, it is broken on newlines.

### Constructor:

    Form.TextPager(form, hgt,wid, row,col, content)

`content` is an iterable of strings or string-like objects, or
one long string.



## List

Subclass of Pager, but the user can highlight and select an item from
the list.

     This is line 0
     This is line 1
    **>This is line 2**
     This is line 3
     This is line 4
     This is line 5

Keyboard interaction is nearly the same as for Pager, except that
ENTER causes the currently-highlit item to be selected, and the
callback, if any, to be called. `handleKey()` will return the
index of the selected item.

### Constructor:

    Form.List(form, hgt,wid, row,col, items)

### setCallback(callback, client)

Specifies the callback to be called when the user selects an item.
The callback is called as `callback(listWidget, index, client)`.

Set `callback` to `None` to disable.

### getCurrent()

Return the index of the currently-highlit item.

### setcurrent(i, row=None)

Highlight the specified item. The widget will adjust the scroll to keep
that item into view. The widget does _not_ redraw after this, so this
function is only used when you intend to completely redraw the widget
later. You probably want to use `moveTo()` instead.

If `row` is specified, the widget always scrolls to place the selected
item at the specified row. Normally you leave this as None and let
the widget choose a reasonable scroll value.

### moveTo(i)

Highlight the specified item. The widget will adjust the scroll to keep
that item into view. The widget does a redraw. Call `refresh()`
after calling this.

### moveBy(i)

Move the highlight by the specified amount.

### moveHome()

Move the highlight to the first item

### moveEnd()

Move the highlight to the last item

### handleKey()

Accept a keystroke. If the keystroke is used by the widget, returns
True.  If the keystroke actually selects a item, calls callback and
returns the index of the selected item.


## OptionsList

Subclass of List, except each item is prefixed by a letter to make quick
selection easy. The prefix letters are a-zA-Z0-9, with some exceptions.

     a INBOX
    **>b Drafts**
     c Sent
     d junk
     e Deleted Messages
     f Trash
     g 3528
     h AGevalia
     i AInvis

Several letters are unavailable, such as 'n' and 'p' because they're
used to navigate the list. You can specify additional letters to
be reserved in the constructor.

### Constructor:

    Form.OptionsList(form, hgt,wid, row,col, items, cmds)

`items` is the list of strings, or string-like objects. `cmds` is a
string of characters to be excluded as prefixes. 'n' and 'p' are
implicitly included in this list.

### isOptionKey(key)

Checks to see if `key` is the prefix character for a list item, and
if so, returns the index of that item. Otherwise returns None.


## ActiveOptionsList

Subclass of OptionsList. Items is a list of objects for which
`str()` returns a reasonable value, and which have an `active()`
method that returns True if the object is selectable. The result
is that inactive items do not have a prefix letter and can't
be highlit.

       start of list
       This is line 0
    **>c This is line 1**
     d This is line 2
       This is line 3
     f This is line 4
       This is line 5
     h This is line 6

### Constructor:

    Form.ActiveOptionsList(form, hgt,wid, row,col, items, cmds)


## ColumnOptionsList

Subclass of OptionsList. Items is a list of of lists of strings to
be displayed in columns.

     a     Do you like soda pop?                          Thomas@cedarville.edu                   2007-09-26 00:36  1624
     b  A  OnlineJobsAvailabeNow                          Brandan.Kopa@mantoni.pl                 2007-10-03 05:14  1243
     c !   Get a lil' extra for the holidays              Debbie                                  2007-12-04 06:08  1418
     e !A  Get a lil' extra for the holidays              Debbie                                  2007-12-04 06:37  1420
     f  U  Fa la la la laptop!                            Debbie                                  2007-12-07 04:40  1483
     g  N  Fa la la la laptop!                            Debbie                                  2007-12-07 05:10  1483
     h  U  Fa la la la laptop!                            Debbie                                  2007-12-11 05:02  1642
     i     Fa la la la laptop!                            Debbie                                  2007-12-11 05:34  1641
    **>j     Last chance to get an iPod for Christmas!      debbie@surveyhometimeforyou.com         2000-01-18 07:46  1721**
     k     Last chance to get an iPod for Christmas!      debbie@surveyhometimeforyou.com         2000-01-18 08:45  1750
     l     Last chance to get an iPod for Christmas!      debbie@surveyhometimeforyou.com         2000-01-19 07:00  1753
     o     Last chance to get an iPod for Christmas!      debbie@surveyhometimeforyou.com         2000-01-19 07:51  1751

By default, the number of columns equals the number of elements in the first
item in the list, and the columns are all equal width. You can change this
behavior by subclassing ColumnOptionsList and overriding resizeColumns().

### Constructor:

    Form.ColumnOptionsList(form, hgt,wid, row,col, items, cmds)

### resizeColumns()

Computes the `cwidths` list which is a list of `(column,width)` pairs, one per
column. See the source code to ColumnOptionsList in forms.py for an
example. If any pair in `cwidths` has a width of zero, that column is
omitted on output. If `cwidths` has fewer items than an item, trailing
elements of that item will be omitted.


----

# Form object

This is the main "container" of the widgets. It tracks which widget currently
has input focus and directs keyboard input to that widget. It also manages
resize events and provides `redraw()` and `refresh()` functions.

### Constructor:

    Form(win, border=True)

Creates a new Form in the specified window. Typically, this will be `stdscr`, but
this is not required. If `border` is True, then a border is created around the entire
form. If you do this, remember to make room for it when positioning widgets.

Note that for the functions below, any function that does not have a specific
return value returns `self`, to allow chaining, e.g. `myform.setWidgets().redraw().refresh()`

### setWidgets(widgets)

Set the form's widget list. `widgets` is a list of Widget objects.

### addWidgets(widgets)

Append the form's widget list.

### resize()

Call this whenever the underlying window size changes. `handleKey()` will
do this automatically if the `key` argument is curses.KEY_RESIZE.

This function calls the `resize()` method of all child widgets.

### redraw()

Execute a complete redraw of the form, clearing the window first, and then
calling the `redraw()` method of all child widgets.

### refresh()

Flush all changes to the screen. Often more efficient than calling
`refresh()` individually on widgets.

### getFocus()

Returns the widget that currently holds focus, or None.

### setFocus(widget)

Move input focus to the specified widget. Widget may be specified as
a widget or an index into the list of widgets.

### nextFocus(widget)

Advance input focus to the next widget

### previousFocus(widget)

Move input focus to the previous widget

### getUchar()

Return one key from the user. This will either be a unicode character or an
integer keycode such as curses.KEY_HOME.

### handleKey(key)

Pass the key to the form's input function. The form initially passes the
key to the currently focused widget to see if that widget wants to
process the key. If so, the form returns whatever that widget
returns. Typically, that value will be True to indicate that the
widget consumed the key but has nothing else to report, or some
other value that is likely meaningful to the application.

Otherwise, the form will respond to the following keys:

* TAB, down-arrow: advance focus to next widget
* Back-TAB, up-arrow: move focus to previous widget
* ^L: redraw the form
* curses.KEY_RESIZE: resize form and redraw.

If none of the above apply, the form returns None, indicating that
it had no use for the key.

### wait()

Enters a loop, calling `getUchar()` and `handleKey()` until
`handleKey()` returns None.

This is not as useful as it sounds since if a widget returns a
meaningful value, it will be ignored and `wait()` will keep on
looping. In practice, you'll write your own input loop:

    while True:
        key = form.getUchar()

        # First handle the keys that we're not even sending to the form
        if key == 'q':
            return
        if key == curses.KEY_F1:
            showHelp()
            form.redraw().refresh()
            continue
        if key == curses.KEY_F2:
            statusLabel.set("Received F2").refresh()
            continue

        # OK, pass it to the form
        rval = form.handleKey(key):
        if rval is not None:
            # OK, some widget responded to the input
            # Or maybe the form itself returned True because
            # this one of the keys it uses directly. To
            # meaningfully process rval, we'll need to know
            # which widget had focus. In general, callbacks
            # or querying the widgets for their current
            # values are an easier way to deal with this.
            ...
