# Simple logging

import sys

# config
enabled = True
file = sys.stderr
_indent = 0

def indent():
    global _indent
    _indent += 2

def dedent():
    global _indent
    _indent -= 2

def task(string):
    if enabled:
        print(" " * _indent + "\033[1;36m" + str(string) + "\033[m", file=file)
        indent()

def log(string):
    if enabled:
        print(" " * _indent + "\033[m" + str(string) + "\033[m", file=file)

def list(l):
    if enabled:
        indent()
        for item in l:
            print(" " * _indent + str(item), file=file)
        dedent()

def success(string):
    if enabled:
        print(" " * _indent + "\033[1;32m" + str(string) + "\033[m", file=file)

def warn(string):
    if enabled:
        print(" " * _indent + "\033[1;33m" + str(string) + "\033[m", file=file)

def error(string):
    if enabled:
        print(" " * _indent + "\033[1;31m" + str(string) + "\033[m", file=file)
