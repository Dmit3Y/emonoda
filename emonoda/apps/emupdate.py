"""
    Emonoda -- A set of tools to organize and manage your torrents
    Copyright (C) 2015  Devaev Maxim <mdevaev@gmail.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import sys
import os
import json
import shutil
import contextlib
import traceback
import threading
import operator
import argparse

from ..plugins.trackers import TrackerError
from ..plugins.trackers import WithCheckHash
from ..plugins.trackers import WithCheckScrape
from ..plugins.trackers import WithCheckTime

from ..helpers import tcollection
from ..helpers import surprise

from .. import tfile
from .. import fmt
from .. import tools

from . import init
from . import get_configured_log
from . import get_configured_client
from . import get_configured_trackers
from . import get_configured_confetti


# =====
class OpContext:
    def __init__(self, torrent, tracker):
        self.torrent = torrent
        self.tracker = tracker

        self._status = None
        self._attrs = {}

    def done_not_in_client(self):
        self._status = "not_in_client"

    def done_affected(self, diff):
        self._status = "affected"
        self._attrs = {"diff": diff}

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc, tb):
        if isinstance(exc, TrackerError):
            self._status = "tracker_error"
            self._attrs = {
                "err_name": type(exc).__name__,
                "err_msg": str(exc),
            }
        elif exc is not None:
            self._status = "unhandled_error"
            self._attrs = {"tb_lines": "".join(traceback.format_exception(exc_type, exc, tb)).strip().split("\n")}
        if self._status is None:
            self._status = "passed"


class Feeder:  # pylint: disable=too-many-instance-attributes
    def __init__(self, trackers, torrents, show_unknown, show_passed, show_diff, log_stdout, log_stderr):
        self._trackers = trackers
        self._torrents = torrents
        self._show_unknown = show_unknown
        self._show_passed = show_passed
        self._show_diff = show_diff
        self._log_stdout = log_stdout
        self._log_stderr = log_stderr

        self._current_count = 0
        self._current_file_name = None
        self._current_torrent = None
        self._current_tracker = None

        self._fan = fmt.make_fan()
        self._fan_thread = None
        self._stop_fan = threading.Event()

        self._status_mapping = {
            "invalid":         self._done_invalid,
            "not_in_client":   self._done_not_in_client,
            "unknown":         self._done_unknown,
            "passed":          self._done_passed,
            "affected":        self._done_affected,
            "tracker_error":   self._done_tracker_error,
            "unhandled_error": self._done_unhandled_error,
        }

        self._results = {status: {} for status in self._status_mapping}

    def get_ops(self):
        for (self._current_count, (self._current_file_name, self._current_torrent)) in enumerate(
            sorted(self._torrents.items(), key=operator.itemgetter(0))
        ):
            self._current_tracker = None

            if self._current_torrent is None:
                self._done("invalid", {})
                continue

            self._current_tracker = self._select_tracker()
            if self._current_tracker is None:
                self._done("unknown", {})
                continue

            op = OpContext(self._current_torrent, self._current_tracker)
            self._start_op()
            yield op
            self._stop_op()
            self._done(op._status, op._attrs)  # pylint: disable=protected-access

        self._log_stdout.finish()

    def get_results(self):
        return self._results

    def _select_tracker(self):
        for tracker in self._trackers:
            if tracker.is_matched_for(self._current_torrent):
                return tracker
        return None

    def _done(self, status, attrs):
        self._status_mapping[status](attrs)
        result = {
            "torrent": self._current_torrent,
            "tracker": self._current_tracker,
        }
        result.update(attrs)
        self._results[status][self._current_file_name] = result

    def _done_invalid(self, _):
        self._log_stdout.print(*self._format_fail("red", "!", "INVALID_TORRENT"))

    def _done_unknown(self, _):
        one_line = (not self._show_unknown and self._log_stdout.isatty())
        self._log_stdout.print(*self._format_fail("yellow", " ", "UNKNOWN"), one_line=one_line)

    def _done_passed(self, _):
        one_line = (not self._show_passed and self._log_stdout.isatty())
        self._log_stdout.print(*self._format_status("blue", " "), one_line=one_line)

    def _done_affected(self, attrs):
        self._log_stdout.print(*self._format_status("green", "+"))
        if self._show_diff:
            self._log_stdout.print(*fmt.format_torrents_diff(attrs["diff"], "\t"))

    def _done_not_in_client(self, _):
        self._log_stdout.print(*self._format_fail("red", "!", "NOT_IN_CLIENT"))

    def _done_tracker_error(self, attrs):
        (line, placeholders) = self._format_status("red", "-")
        line += " :: {red}%s({reset}%s{red}){reset}"
        placeholders += (attrs["err_name"], attrs["err_msg"])
        self._log_stdout.print(line, placeholders)

    def _done_unhandled_error(self, attrs):
        self._log_stdout.print(*self._format_status("red", "-"))
        self._log_stdout.print("%s", ("\n".join("\t" + row for row in attrs["tb_lines"]),))

    def _start_op(self):
        if self._log_stdout.isatty():
            def loop():
                while not self._stop_fan.wait(timeout=0.1):
                    self._log_stdout.print(*self._format_status("magenta", next(self._fan)), one_line=True)
            self._fan_thread = threading.Thread(target=loop, daemon=True)
            self._fan_thread.start()
        else:
            self._log_stdout.print(*self._format_status("magenta", " "))

    def _stop_op(self):
        if self._fan_thread is not None:
            self._stop_fan.set()
            self._fan_thread.join()
            self._stop_fan.clear()

    def _format_fail(self, color, sign, error):
        return (
            "[{" + color + "}%s{reset}] %s {" + color + "}%s {cyan}%s{reset}",
            (sign, self._format_progress(), error, self._current_file_name),
        )

    def _format_status(self, color, sign):
        return (
            "[{" + color + "}%s{reset}] %s {" + color + "}%s {cyan}%s{reset} -- %s",
            (
                sign, self._format_progress(), self._current_tracker.PLUGIN_NAME,
                self._current_file_name, (self._current_torrent.get_comment() or ""),
            ),
        )

    def _format_progress(self):
        return fmt.format_progress(self._current_count + 1, len(self._torrents))


def backup_torrent(torrent, backup_dir_path, backup_suffix):
    backup_suffix = fmt.format_now(backup_suffix)
    backup_file_path = os.path.join(backup_dir_path, os.path.basename(torrent.get_path()) + backup_suffix)
    shutil.copyfile(torrent.get_path(), backup_file_path)


@contextlib.contextmanager
def client_hooks(client, torrent, to_save_customs, to_set_customs):
    if client is not None:
        prefix = client.get_data_prefix(torrent)
        if len(to_save_customs) != 0:
            customs = client.get_customs(torrent, to_save_customs)
        else:
            customs = {}
        meta_file_path = tools.make_sub_name(torrent.get_path(), ".", ".meta")
        with open(meta_file_path, "w") as meta_file:
            meta_file.write(json.dumps({
                "prefix": prefix,
                "customs": customs,
            }))
        client.remove_torrent(torrent)

    yield  # Torrent-object was changed

    if client is not None:
        client.load_torrent(torrent, prefix)
        customs.update({
            key: fmt.format_now(value)
            for (key, value) in to_set_customs.items()
        })
        if len(customs) != 0:
            client.set_customs(torrent, customs)
        os.remove(meta_file_path)


def update_torrent(client, torrent, new_data, to_save_customs, to_set_customs):
    data_file_path = tools.make_sub_name(torrent.get_path(), ".", ".newdata")
    with open(data_file_path, "wb") as data_file:
        data_file.write(new_data)
    with client_hooks(client, torrent, to_save_customs, to_set_customs):
        os.replace(data_file_path, torrent.get_path())
        torrent.load_from_data(new_data, torrent.get_path())


class TorrentTimeInfo:
    def __init__(self, torrent):
        self._torrent = torrent
        self._time_file_path = tools.make_sub_name(self._torrent.get_path(), ".", ".time")

    def check_and_fill(self):
        if not os.path.exists(self._time_file_path):
            self.write(int(os.stat(self._torrent.get_path()).st_mtime))
        return self

    def read(self):
        with open(self._time_file_path) as time_file:
            return int(time_file.read().strip())

    def write(self, value):
        with open(self._time_file_path, "w") as time_file:
            time_file.write(str(int(value)))


def update(  # pylint: disable=too-many-branches
    feeder,
    client,
    backup_dir_path,
    backup_suffix,
    to_save_customs,
    to_set_customs,
    noop,
):
    hashes = (client.get_hashes() if client is not None else [])
    for op in feeder.get_ops():
        try:
            with op:
                if client is not None and op.torrent.get_hash() not in hashes:
                    op.done_not_in_client()
                    continue

                tracker_bases = op.tracker.get_bases()

                if WithCheckHash in tracker_bases:
                    need_update = (op.tracker.fetch_hash(op.torrent) != op.torrent.get_hash())

                elif WithCheckScrape in tracker_bases:
                    need_update = (not op.tracker.is_registered(op.torrent))

                elif WithCheckTime in tracker_bases:
                    time_info = TorrentTimeInfo(op.torrent).check_and_fill()
                    tracker_time = op.tracker.fetch_time(op.torrent)
                    need_update = (tracker_time > time_info.read())

                else:
                    RuntimeError("Invalid tracker {}: missing method of check".format(op.tracker))

                if need_update:
                    tmp_torrent = tfile.Torrent(data=op.tracker.fetch_new_data(op.torrent))
                    if op.torrent.get_hash() != tmp_torrent.get_hash():
                        diff = tfile.get_difference(op.torrent, tmp_torrent)
                        if not noop:
                            if backup_dir_path is not None:
                                backup_torrent(op.torrent, backup_dir_path, backup_suffix)
                            update_torrent(client, op.torrent, tmp_torrent.get_data(), to_save_customs, to_set_customs)
                            if WithCheckTime in tracker_bases:
                                time_info.write(tracker_time)
                        op.done_affected(diff)
                    elif WithCheckTime in tracker_bases and not noop:
                        time_info.write(tracker_time)
        except Exception:
            pass


def print_results(results, log):
    for (msg, field) in (
        ("Updated:          %d", "affected"),
        ("Passed:           %d", "passed"),
        ("Not in client:    %d", "not_in_client"),
        ("Unknown:          %d", "unknown"),
        ("Invalid torrents: %d", "invalid"),
        ("Tracker errors:   %d", "tracker_error"),
        ("Unhandled errors: %d", "unhandled_error"),
    ):
        log.info(msg, (len(results[field]),))


# ===== Main =====
def main():
    (parent_parser, argv, config) = init()
    args_parser = argparse.ArgumentParser(
        prog="emupdate",
        description="Update torrent files from popular trackers",
        parents=[parent_parser],
    )
    args_parser.add_argument("-f", "--name-filter", default=None, metavar="<wildcard_pattern>")
    args_parser.add_argument("-y", "--only-trackers", default=[], nargs="+", metavar="<tracker>")
    args_parser.add_argument("-x", "--exclude-trackers", default=[], nargs="+", metavar="<tracker>")
    args_parser.add_argument("--noop", action="store_true")
    args_parser.add_argument("--mute", action="store_true")
    args_parser.add_argument("--fail-on-captcha", action="store_true")
    options = args_parser.parse_args(argv[1:])

    with get_configured_log(config, False, sys.stdout) as log_stdout:
        with get_configured_log(config, False, sys.stderr) as log_stderr:

            client = get_configured_client(
                config=config,
                required=False,
                with_customs=(len(config.emupdate.save_customs) or len(config.emupdate.set_customs)),
                log=log_stderr,
            )

            def read_captcha(url):
                if options.fail_on_captcha:
                    raise RuntimeError("Required decoding of captcha but '--fail-on-captcha' specified")
                else:
                    log_stderr.info("{yellow}Enter the captcha{reset} from [{blue}%s{reset}]: ", (url,), no_nl=True)
                    return input()

            trackers = get_configured_trackers(
                config=config,
                captcha_decoder=read_captcha,
                only=options.only_trackers,
                exclude=options.exclude_trackers,
                log=log_stderr,
            )

            if not options.mute:
                confetti = get_configured_confetti(
                    config=config,
                    log=log_stderr,
                )

            torrents = tcollection.load_from_dir(
                path=config.core.torrents_dir,
                name_filter=(options.name_filter or config.emupdate.name_filter),
                log=log_stderr,
            )

            feeder = Feeder(
                trackers=trackers,
                torrents=torrents,
                show_unknown=config.emupdate.show_unknown,
                show_passed=config.emupdate.show_passed,
                show_diff=config.emupdate.show_diff,
                log_stdout=log_stdout,
                log_stderr=log_stderr,
            )

            update(
                feeder=feeder,
                client=client,
                backup_dir_path=config.emupdate.backup_dir,
                backup_suffix=config.emupdate.backup_suffix,
                to_save_customs=config.emupdate.save_customs,
                to_set_customs=config.emupdate.set_customs,
                noop=options.noop,
            )

            results = feeder.get_results()
            print_results(
                results=results,
                log=log_stderr,
            )
            if not options.mute:
                if len(results["affected"]) != 0:
                    if not surprise.deploy_surprise(
                        source="emupdate",
                        results=results,
                        confetti=confetti,
                        log=log_stderr,
                    ):
                        raise SystemExit(1)


if __name__ == "__main__":
    main()  # Do the thing!
