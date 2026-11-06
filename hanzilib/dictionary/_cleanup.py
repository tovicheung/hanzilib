from __future__ import annotations

"""Remove queued files after the requesting process has exited."""

import ctypes
import os
import sys
from ctypes import wintypes


def _wait_for_process_exit(process_id: int) -> None:
	if os.name != "nt":
		return

	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.OpenProcess.argtypes = [
		wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
	]
	kernel32.OpenProcess.restype = wintypes.HANDLE
	kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
	kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
	process = kernel32.OpenProcess(0x00100000, False, process_id)
	if not process:
		return
	try:
		kernel32.WaitForSingleObject(process, 0xFFFFFFFF)
	finally:
		kernel32.CloseHandle(process)


def main() -> None:
	process_id = int(sys.argv[1])
	paths = sys.argv[2:]
	_wait_for_process_exit(process_id)
	for path in paths:
		try:
			os.remove(path)
		except FileNotFoundError:
			pass


if __name__ == "__main__":
	main()
