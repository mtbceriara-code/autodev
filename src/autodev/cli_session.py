"""CLI handlers for tmux session management commands."""

from __future__ import annotations

import argparse
import os
import sys


def cmd_list(args: argparse.Namespace) -> int:
    """Handle ``autodev list`` — show running autodev tmux sessions."""
    from autodev.tmux_session import check_tmux_available, list_autodev_sessions

    err = check_tmux_available()
    if err:
        print(err, file=sys.stderr)
        return 1

    sessions = list_autodev_sessions()
    if not sessions:
        print("No running autodev sessions.")
        return 0

    print(f"{'SESSION':<40} {'WINDOWS':<10} {'CREATED'}")
    print("-" * 70)
    for s in sessions:
        print(f"{s['name']:<40} {s['windows']:<10} {s['created']}")
    return 0


def cmd_attach(args: argparse.Namespace) -> int:
    """Handle ``autodev attach <session>`` — attach to a tmux session."""
    from autodev.tmux_session import check_tmux_available, is_session_alive

    err = check_tmux_available()
    if err:
        print(err, file=sys.stderr)
        return 1

    session = args.session
    if not is_session_alive(session):
        print(f"Session '{session}' not found. Run 'autodev list' to see available sessions.",
              file=sys.stderr)
        return 1

    os.execvp("tmux", ["tmux", "attach-session", "-t", session])
    return 0  # unreachable, but satisfies type checker


def cmd_stop(args: argparse.Namespace) -> int:
    """Handle ``autodev stop <session>`` or ``autodev stop --all``."""
    from autodev.tmux_session import check_tmux_available, kill_all_sessions, kill_session

    err = check_tmux_available()
    if err:
        print(err, file=sys.stderr)
        return 1

    if getattr(args, "all", False):
        killed = kill_all_sessions()
        if killed:
            print(f"Stopped {killed} session(s).")
        else:
            print("No running autodev sessions to stop.")
        return 0

    session = getattr(args, "session", None)
    if not session:
        print("Specify a session name or use --all.", file=sys.stderr)
        return 1

    if kill_session(session):
        print(f"Stopped session: {session}")
        return 0
    else:
        print(f"Session '{session}' not found.", file=sys.stderr)
        return 1
