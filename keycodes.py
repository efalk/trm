import sys

PY3 = sys.version_info[0] >= 3
if PY3:
    unicode = str
    unichr = chr

def CTRL(c): return unichr(ord(c)-0100)     # TODO: support non-ascii?
ESC = unichr(033)
CTRL_B = CTRL('B')
CTRL_E = CTRL('E')
CTRL_F = CTRL('F')
CTRL_L = CTRL('L')
CTRL_N = CTRL('N')
CTRL_P = CTRL('P')
CTRL_R = CTRL('R')
CTRL_U = CTRL('U')
CTRL_Y = CTRL('Y')
KEY_TAB = CTRL('I')
