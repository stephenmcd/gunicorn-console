#!/usr/bin/env python

import curses
from itertools import count
from subprocess import Popen, PIPE

__version__ = "0.1"

gunicorns = {} # gunicorn master process names/pids.
selected = None # Name of currently selected gunicorn master process.
screen_delay = .01 # Seconds between screen updates.
ps_delay = 2 # Seconds between ps updates.
tick = 0 # Internal counter incremented in main event loop.
title = "(`\._./`\._.-> gunicorn-console <-._./`\._./`)"
instructions = """(r)eload master | (a)dd worker
kill (w)orker | kill (m)aster | (q)uit
up/down changes selection
"""
no_gunicorns = "Aww, no gunicorns are running!!"
screen_width = None
foreground_colour = curses.COLOR_BLACK
background_colour = curses.COLOR_BLUE


def send_signal(signal):
    """
    Send the signal to the selected master gunicorn process and show the given 
    message as the current status.
    """
    if selected in gunicorns:
        Popen(["kill", "-%s" % signal, gunicorns[selected]["pid"]])
    curses.flash()
        
def move_selection(reverse=False):
    """
    Goes through the list of gunicorns, setting the selected as the one after 
    the currently selected.
    """
    global selected
    if selected not in gunicorns:
        selected = None
    found = False
    items = sorted(gunicorns.keys(), reverse=reverse)
    # Iterate items twice to enable wrapping.
    for name in items + items: # 
        if selected is None or found:
            selected = name
            return
        elif name == selected:
            found = True

def update_gunicorns(): 
    """
    Updates the dict of gunicorn processes.
    """
    global tick, gunicorns
    if (tick * screen_delay) % ps_delay == 0:
        tick = 0
        gunicorns = {}
        ps = Popen(["ps", "vx"], stdout=PIPE).communicate()[0].split("\n")
        headings = ps.pop(0).split()
        pid_col = headings.index("PID")
        name_col = headings.index("COMMAND")
        mem_col = headings.index("RSS")
        num_cols = len(headings) - 1
        for row in ps:
            cols = row.split(None, num_cols)
            if cols and cols[name_col].startswith("gunicorn: "):
                name = cols[name_col].strip().split("[", 1)[1][:-1]
                if name not in gunicorns:
                    gunicorns[name] = {"pid": None, "workers": 0, "mem": 0}
                if cols[name_col].startswith("gunicorn: master"):
                    gunicorns[name]["pid"] = cols[pid_col]
                elif cols[name_col].startswith("gunicorn: worker"):
                    gunicorns[name]["workers"] += 1
                gunicorns[name]["mem"] += int(cols[mem_col])
    tick += 1

def handle_keypress(screen):
    """
    Check for a key being pressed and handle it if applicable.
    """
    try:
        key = screen.getkey().upper()
    except:
        return
    if key == "KEY_DOWN":
        move_selection()
    elif key == "KEY_UP":
        move_selection(reverse=True)
    elif key in ("A", "+"):
        send_signal("TTIN")
        gunicorns[selected]["workers"] = 0
    elif key in ("W", "-"):
        if gunicorns[selected]["workers"] != 1:
            send_signal("TTOU")
            gunicorns[selected]["workers"] = 0
    elif key in ("R",):
        send_signal("HUP")
        del gunicorns[selected]
    elif key in ("M", "-"):
        send_signal("QUIT")
        del gunicorns[selected]
    elif key in ("Q",):
        raise KeyboardInterrupt

def format_row(pid, name, mem, workers):
    """
    Applies consistant padding to each of the columns in a row.
    """
    row = " %s %s %s %s " % (str(pid).ljust(5), str(name).ljust(31), 
        str(mem).rjust(8), str(workers).rjust(7))
    global screen_width
    if screen_width is None:
        screen_width = len(row)
    return row

def display_output(screen):
    """
    Display the menu list of gunicorns and the status message.
    """
    format_row("", "", "", "")
    screen_height = len(gunicorns) + len(instructions.split("\n")) + 9
    if not gunicorns:
        screen_height += 2
    win = curses.newwin(screen_height, screen_width + 6, 1, 3)
    win.bkgd(" ", curses.color_pair(1))
    win.border()
    x = 3
    blank_line = y = count(2).next
    win.addstr(y(), x, title.center(screen_width), curses.A_NORMAL)
    blank_line()
    win.addstr(y(), x, format_row("PID", "NAME", "MEM (MB)", "WORKERS"), 
        curses.A_STANDOUT)
    if not gunicorns:
        blank_line()
        win.addstr(y(), x, no_gunicorns.center(screen_width), 
            curses.A_NORMAL)
        blank_line()
    else:
        win.hline(y(), x, curses.ACS_HLINE, screen_width)
        for i, name in enumerate(sorted(gunicorns.keys())):
            pid = gunicorns[name]["pid"]
            mem = "%#.3f" % (gunicorns[name]["mem"] / 1000.)
            workers = gunicorns[name]["workers"]
            # When a signal is sent to update the number of workers, the number 
            # of workers is set to zero as a marker to signify an update has 
            # occurred. We then piggyback this variable and use it as a counter 
            # to animate the display until the gunicorn is next updated.
            if workers < 1:
                if tick % 7 == 0: # Slightly delay the animation.
                    gunicorns[name]["workers"] -= 1
                chars = "|/-\\"
                workers *= -1
                if workers == len(chars):
                   gunicorns[name]["workers"] = workers = 0 
                workers = chars[workers]
            if name == selected:
                attr = curses.A_STANDOUT
            else:
                attr = curses.A_NORMAL
            win.addstr(y(), x, format_row(pid, name, mem, workers), attr)
    win.hline(y(), x, curses.ACS_HLINE, screen_width)
    blank_line()
    for line in instructions.split("\n"):
        win.addstr(y(), x, line.center(screen_width), curses.A_NORMAL)
    win.refresh()

if __name__ == "__main__":
    # Set up curses.
    stdscr = curses.initscr()
    curses.start_color()
    curses.init_pair(1, foreground_colour, background_colour)
    curses.noecho()
    stdscr.keypad(True)
    stdscr.nodelay(True)
    curses.curs_set(False)
    # Run main event loop until quit.
    while True:
        try:
            update_gunicorns()
            handle_keypress(stdscr)
            display_output(stdscr)
            curses.napms(int(screen_delay * 1000))
        except KeyboardInterrupt:
            break
    # Tear down curses.
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()

