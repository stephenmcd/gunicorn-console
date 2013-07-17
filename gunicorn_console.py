#!/usr/bin/env python

import re
import curses
from itertools import count
from subprocess import Popen, PIPE
from sys import platform, exit


__version__ = "0.1.16"

gunicorns = {} # gunicorn master process names/pids.
selected_pid = None # Process ID of currently selected gunicorn master process.
screen_delay = .1 # Seconds between screen updates.
ps_delay = 2 # Seconds between ps updates.
tick = -1 # Internal counter incremented in main event loop.
title = "(`\._./`\._.-> gunicorn-console <-._./`\._./`)"
instructions = """(r)eload master | (t)otal reload | (a)dd worker
kill (w)orker | kill (m)aster | (q)uit
up/down changes selection
"""
no_gunicorns = "Aww, no gunicorns are running!!"
screen_width = None
foreground_colour = curses.COLOR_BLACK
background_colour = curses.COLOR_GREEN

cmd_heading = "CMD"

if re.search("freebsd|openbsd", platform):
    cmd_heading = "COMMAND"

if re.search("darwin|freebsd|openbsd", platform):
    PS_ARGS = ["ps", "-lx"]

    def ports_for_pids(pids):
        LSOF_ARGS = ["lsof", "-i", "-n", "-P"]
        # lsof is an external command, so won't always be present
        try:
            lsof = Popen(LSOF_ARGS, stdout=PIPE,
                stderr=PIPE).communicate()[0].split("\n")
        except:
            return
        addr_pos = None
        pid_pos = None
        addr_heading = "NAME"
        pid_heading = "PID"
        for row in lsof:
            if addr_heading in row and pid_heading in row:
                addr_pos = row.index(addr_heading)
                pid_pos = row.index(pid_heading)-2
            if addr_pos is not None:
                pid = row[pid_pos:].split(" ")[0]
                if pid in pids:
                    port = row[addr_pos:].split(":")[1].split(" ", 1)[0]
                    yield (pid, port)
else:
    PS_ARGS = ["ps", "x", "-Fe"]

    def ports_for_pids(pids):
        netstat = Popen(["netstat","-lpn"], stdout=PIPE,
            stderr=PIPE).communicate()[0].split("\n")
        addr_pos = None
        pid_pos = None
        addr_heading = "Local Address"
        pid_heading = "PID/Program name"
        for row in netstat:
            if addr_heading in row and pid_heading in row:
                addr_pos = row.index(addr_heading)
                pid_pos = row.index(pid_heading)
            if addr_pos is not None:
                pid = row[pid_pos:].split("/")[0]
                if pid in pids:
                    port = row[addr_pos:].split(" ", 1)[0].split(":")[1]
                    yield (pid, port)


def send_signal(signal):
    """
    Send the signal to the selected master gunicorn process and show the given
    message as the current status.
    """
    if selected_pid in gunicorns:
        Popen(["kill", "-%s" % signal, selected_pid])
    curses.flash()


def move_selection(reverse=False):
    """
    Goes through the list of gunicorns, setting the selected as the one after
    the currently selected.
    """
    global selected_pid
    if selected_pid not in gunicorns:
        selected_pid = None
    found = False
    pids = sorted(gunicorns.keys(), reverse=reverse)
    # Iterate items twice to enable wrapping.
    for pid in pids + pids:
        if selected_pid is None or found:
            selected_pid = pid
            return
        found = pid == selected_pid


def update_gunicorns():
    """
    Updates the dict of gunicorn processes. Run the ps command and parse its
    output for processes named after gunicorn, building up a dict of gunicorn
    processes. When new gunicorns are discovered, run the netstat command to
    determine the ports they're serving on.
    """
    global tick
    tick += 1
    if (tick * screen_delay) % ps_delay != 0:
        return
    tick = 0
    for pid in gunicorns:
        gunicorns[pid].update({"workers": 0, "mem": 0})
    ps = Popen(PS_ARGS, stdout=PIPE).communicate()[0].split("\n")
    headings = ps.pop(0).split()
    name_col = headings.index(cmd_heading)
    num_cols = len(headings) - 1
    for row in ps:
        cols = row.split(None, num_cols)
        if cols and "gunicorn: " in cols[name_col]:
            if "gunicorn: worker" in cols[name_col]:
                is_worker = True
            else:
                is_worker = False

            if is_worker:
                pid = cols[headings.index("PPID")]
            else:
                pid = cols[headings.index("PID")]
            if pid not in gunicorns:
                gunicorns[pid] = {"workers": 0, "mem": 0, "port": None, "name":
                    cols[name_col].strip().split("[",1)[1].split("]",1)[:-1]}
            gunicorns[pid]["mem"] += int(cols[headings.index("RSS")])
            if is_worker:
                gunicorns[pid]["workers"] += 1
    # Remove gunicorns that were not found in the process list.
    for pid in gunicorns.keys()[:]:
        if gunicorns[pid]["workers"] == 0:
            del gunicorns[pid]
    # Determine ports if any are missing.
    if not [g for g in gunicorns.values() if g["port"] is None]:
        return
    for (pid, port) in ports_for_pids(gunicorns.keys()):
        if pid in gunicorns:
            gunicorns[pid]["port"] = port


def handle_keypress(screen):
    """
    Check for a key being pressed and handle it if applicable.
    """
    global selected_pid
    try:
        key = screen.getkey().upper()
    except:
        return
    if key in ("KEY_DOWN", "J"):
        move_selection()
    elif key in ("KEY_UP", "K"):
        move_selection(reverse=True)
    elif key in ("A", "+"):
        send_signal("TTIN")
        if selected_pid in gunicorns:
            gunicorns[selected_pid]["workers"] = 0
    elif key in ("W", "-"):
        if selected_pid in gunicorns:
            if gunicorns[selected_pid]["workers"] != 1:
                send_signal("TTOU")
                gunicorns[selected_pid]["workers"] = 0
    elif key in ("R",):
        if selected_pid in gunicorns:
            send_signal("HUP")
            del gunicorns[selected_pid]
            selected_pid = None
    elif key in ("T",):
        for pid in gunicorns.copy().iterkeys():
            selected_pid = pid
            send_signal("HUP")
            del gunicorns[selected_pid]
            selected_pid = None
    elif key in ("M", "-"):
        if selected_pid in gunicorns:
            send_signal("QUIT")
            del gunicorns[selected_pid]
            selected_pid = None
    elif key in ("Q",):
        raise KeyboardInterrupt


def format_row(pid="", port="", name="", mem="", workers="", prefix_char="  "):
    """
    Applies consistant padding to each of the columns in a row and serves as
    the source of the overall screen width.
    """
    row = "%s%-5s %-6s %-25s %8s %7s " \
          % (prefix_char, pid, port, name, mem, workers)

    global screen_width
    if screen_width is None:
        screen_width = len(row)
    return row


def display_output(screen):
    """
    Display the menu list of gunicorns.
    """
    format_row() # Sets up the screen width.
    screen_height = len(gunicorns) + len(instructions.split("\n")) + 9
    if not gunicorns:
        screen_height += 2 # A couple of blank lines are added when empty.
    screen.erase()
    win = curses.newwin(screen_height, screen_width + 6, 1, 3)
    win.bkgd(" ", curses.color_pair(1))
    win.border()
    x = 3
    blank_line = y = count(2).next
    win.addstr(y(), x, title.center(screen_width), curses.A_NORMAL)
    blank_line()
    win.addstr(y(), x, format_row(" PID", "PORT", "NAME", "MEM (MB)", "WORKERS"),
        curses.A_STANDOUT)
    if not gunicorns:
        blank_line()
        win.addstr(y(), x, no_gunicorns.center(screen_width),
            curses.A_NORMAL)
        blank_line()
    else:
        win.hline(y(), x, curses.ACS_HLINE, screen_width)
        for (i, pid) in enumerate(sorted(gunicorns.keys())):
            port = gunicorns[pid]["port"]
            name = gunicorns[pid]["name"]
            mem = "%#.3f" % (gunicorns[pid]["mem"] / 1000.)
            workers = gunicorns[pid]["workers"]
            # When a signal is sent to update the number of workers, the number
            # of workers is set to zero as a marker to signify an update has
            # occurred. We then piggyback this variable and use it as a counter
            # to animate the display until the gunicorn is next updated.
            if workers < 1:
                gunicorns[pid]["workers"] -= 1
                chars = "|/-\\"
                workers *= -1
                if workers == len(chars):
                   gunicorns[pid]["workers"] = workers = 0
                workers = chars[workers]
            if pid == selected_pid:
                attr = curses.A_STANDOUT
                prefix_char = '> '
            else:
                attr = curses.A_NORMAL
                prefix_char = '  '
            win.addstr(y(), x, format_row(pid, port, name, mem, workers,
                                          prefix_char), attr)
    win.hline(y(), x, curses.ACS_HLINE, screen_width)
    blank_line()
    for line in instructions.split("\n"):
        win.addstr(y(), x, line.center(screen_width), curses.A_NORMAL)
    win.refresh()


def main():
    """
    Main entry point for gunicorn_console.
    """
    # Set up curses.
    stdscr = curses.initscr()
    curses.start_color()
    curses.init_pair(1, foreground_colour, background_colour)
    curses.noecho()
    stdscr.keypad(True)
    stdscr.nodelay(True)
    try:
        curses.curs_set(False)
    except:
        pass
    try:
        # Run main event loop until quit.
        while True:
            try:
                update_gunicorns()
                handle_keypress(stdscr)
                display_output(stdscr)
                curses.napms(int(screen_delay * 1000))
            except KeyboardInterrupt:
                break
    finally:
        # Tear down curses.
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()


if __name__ == "__main__":
    try:
        import setproctitle
    except ImportError:
        print
        print "\033[91mError: You must install the setproctitle package.\033[0m"
        print
        exit()
    main()
