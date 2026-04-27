# Simple lightweight logging

import sys

# config
enabled = True
file = sys.stderr

def task(string):
    if enabled:
        print("\033[1;36m" + str(string) + "\033[m", file=file)

def log(string):
    if enabled:
        print("  " + str(string) + "\033[m", file=file)

def list(l):
    if enabled:
        for item in l:
            print("    " + str(item), file=file)

def success(string):
    if enabled:
        print("  \033[1;32m" + str(string) + "\033[m", file=file)

def warn(string):
    if enabled:
        print("  \033[1;33m" + str(string) + "\033[m", file=file)

def error(string):
    if enabled:
        print("  \033[1;31m" + str(string) + "\033[m", file=file)
