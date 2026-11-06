from __future__ import annotations

"""Uninstall dictionaries from a database and remove downloaded data."""

__all__ = ["uninstall_dictionaries", "main"]

import argparse
import os
import subprocess
import sys
from collections.abc import Iterable, Sequence
from urllib.parse import urlsplit

from sqlalchemy.engine.url import make_url

from hanzilib import dbconnector, log
from hanzilib.dictionary.install import (
	DictionaryInstaller,
	getDownloaderClass,
	getProjectDataPath,
)


def _uninstall_from_database(db: dbconnector.DatabaseConnector, dictionary_name: str) -> bool:
	removed = False
	if db.hasTable(dictionary_name):
		table = db.tables[dictionary_name]
		table.drop(bind=db.connection)
		removed = True

	if db.hasTable("Version"):
		version_table = db.tables["Version"]
		result = db.execute(version_table.delete().where(
			version_table.c.TableName == dictionary_name
		))
		removed = removed or result.rowcount > 0

	return removed


def _get_downloaded_data_path(dictionary_name: str) -> str:
	downloader_class = getDownloaderClass(dictionary_name)
	file_name = getattr(downloader_class, "DOWNLOAD_FILE_NAME", None)
	if file_name is None:
		download_link = getattr(downloader_class, "DOWNLOAD_LINK", None)
		if download_link is None:
			raise ValueError(
				"No local download filename is configured for %s" % dictionary_name
			)
		file_name = os.path.basename(urlsplit(download_link).path)

	return os.path.join(getProjectDataPath(), os.path.basename(file_name))


def _schedule_windows_cleanup(paths: Sequence[str]) -> None:
	subprocess.Popen(
		[
			sys.executable,
			"-m",
			"hanzilib.dictionary._cleanup",
			str(os.getpid()),
			*paths,
		],
		stdin=subprocess.DEVNULL,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
		close_fds=True,
		creationflags=(
			subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
		),
	)


def uninstall_dictionaries(
	dictionary_names: Iterable[str],
	*,
	quiet: bool = True,
	database_url: str | None = None,
	db_connect_inst=None,
	local: bool = False,
	prefix: str | None = None,
	attach: Sequence[str] = (),
	register_unicode: bool | str | None = None,
) -> list[bool]:
	"""Uninstall dictionaries, reusing one connection for each database URL.

	Results correspond to the input names and are true when database state or a
	local downloaded file was removed or queued for removal. An explicit
	``database_url`` lets multiple dictionary tables share one connector. The
	default installer URL is dictionary-specific, so it may require a separate
	connector for each name.
	"""
	names = list(dictionary_names)
	for dictionary_name in names:
		getDownloaderClass(dictionary_name)

	if db_connect_inst is not None and database_url is not None:
		raise ValueError("Specify either db_connect_inst or database_url, not both")

	results = [False] * len(names)
	if not names:
		return results

	if db_connect_inst is not None:
		groups = [(None, list(enumerate(names)))]
	else:
		grouped_names: dict[str, list[tuple[int, str]]] = {}
		for index, dictionary_name in enumerate(names):
			target_url = database_url or DictionaryInstaller.getDefaultDatabaseUrl(
				dictionary_name,
				prefix=prefix,
				local=local,
			)
			grouped_names.setdefault(target_url, []).append(
				(index, dictionary_name)
			)
		groups = list(grouped_names.items())

	for target_url, grouped_entries in groups:
		owns_db = db_connect_inst is None
		database_path = None
		if owns_db:
			url = make_url(target_url)
			if (url.drivername.startswith("sqlite") and url.database
					and url.database != ":memory:"
					and not os.path.exists(url.database)):
				continue
			if (database_url is None and url.drivername.startswith("sqlite")
					and url.database and url.database != ":memory:"
					and url.query.get("mode") != "memory"):
				database_path = url.database

			configuration = {
				"sqlalchemy.url": target_url,
				"attach": [attach] if isinstance(attach, str) else list(attach),
			}
			if register_unicode is not None:
				configuration["registerUnicode"] = register_unicode
			db = dbconnector.DatabaseConnector(configuration)
		else:
			db = db_connect_inst
			if len(grouped_entries) == 1:
				_, dictionary_name = grouped_entries[0]
				url = make_url(db.databaseUrl)
				default_url = make_url(
					DictionaryInstaller.getDefaultDatabaseUrl(
						dictionary_name,
						prefix=prefix,
						local=local,
					)
				)
				if (url == default_url and url.drivername.startswith("sqlite")
						and url.database and url.database != ":memory:"
						and url.query.get("mode") != "memory"):
					database_path = url.database

		try:
			for index, dictionary_name in grouped_entries:
				results[index] = _uninstall_from_database(db, dictionary_name)

			if owns_db:
				db.connection.commit()
		except Exception:
			if owns_db:
				db.connection.rollback()
			raise
		finally:
			if owns_db:
				db.connection.close()
				db.engine.dispose()

		if database_path is not None:
			pending_paths = []
			for path in (database_path, database_path + "-journal",
					database_path + "-wal", database_path + "-shm"):
				try:
					os.remove(path)
				except FileNotFoundError:
					continue
				except PermissionError as exc:
					if (os.name != "nt"
							or getattr(exc, "winerror", None) not in (32, 33)):
						raise
					pending_paths.append(path)
				else:
					for index, _ in grouped_entries:
						results[index] = True
			if pending_paths:
				_schedule_windows_cleanup(pending_paths)
				for index, _ in grouped_entries:
					results[index] = True

	for index, dictionary_name in enumerate(names):
		data_path = _get_downloaded_data_path(dictionary_name)
		try:
			os.remove(data_path)
		except FileNotFoundError:
			pass
		else:
			results[index] = True

		if not quiet:
			if results[index]:
				log.log("Uninstalled dictionary %s" % dictionary_name)
			else:
				log.log("Dictionary %s is not installed" % dictionary_name)

	return results


def run(args: Sequence[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Uninstall dictionaries.")
	parser.add_argument("names", nargs="+", metavar="DICTIONARY")
	parser.add_argument("--local", action="store_true",
		help="remove from the user directory")
	parser.add_argument("--prefix", metavar="PREFIX",
		help="installation prefix (Unix only)")
	parser.add_argument("--database", dest="database_url", metavar="URL",
		help="database URL")
	parser.add_argument("--attach", action="append", default=[], metavar="URL",
		help="attachable database URL or project name")
	parser.add_argument("-q", "--quiet", action="store_true",
		help="don't print status information")
	options = parser.parse_args(args)

	try:
		uninstall_dictionaries(
			options.names,
			quiet=options.quiet,
			database_url=options.database_url,
			local=options.local,
			prefix=options.prefix,
			attach=options.attach,
		)
	except Exception as exc:
		log.error("Error uninstalling dictionaries: %s" % exc)
		return 1
	return 0


def main(args: Sequence[str] | None = None) -> None:
	try:
		sys.exit(run(args))
	except KeyboardInterrupt:
		print("Keyboard interrupt.", file=sys.stderr)
		sys.exit(1)


if __name__ == "__main__":
	main()
