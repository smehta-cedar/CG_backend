#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

from decouple import config

STARTAPP_VALUE_FLAGS = {
    "--template",
    "--extension",
    "-e",
    "--name",
    "-n",
    "--exclude",
    "-x",
}


def _startapp_positionals():
    skip_next = False
    positionals = []
    for arg in sys.argv[2:]:
        if skip_next:
            skip_next = False
            continue
        if arg in STARTAPP_VALUE_FLAGS:
            skip_next = True
            continue
        if arg.startswith("-"):
            continue
        positionals.append(arg)
    return positionals


def _place_startapp_in_apps_dir():
    """Create new apps under apps/ unless a destination is already given."""
    if len(sys.argv) < 2 or sys.argv[1] != "startapp":
        return
    if len(_startapp_positionals()) != 1:
        return
    os.chdir(Path(__file__).resolve().parent / "apps")


def main():
    """Run administrative tasks."""
    os.environ["DJANGO_SETTINGS_MODULE"] = config("DJANGO_SETTINGS_MODULE")
    _place_startapp_in_apps_dir()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
