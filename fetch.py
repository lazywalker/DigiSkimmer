#!/usr/bin/env python3
# -*- python -*-
#
# Copyright(c) 2020 BD7MQB Michael Choi <bd7mqb@qq.com>
# This is free software, licensed under the GNU GENERAL PUBLIC LICENSE, Version 2.0
#

from digiskr import Option, Config
from kiwi import KiwiWorker
import timespan
from digiskr import config, DecoderQueue
from digiskr.pskreporter import PskReporter
from digiskr.wsprnet import Wsprnet
from digiskr.audio import WsjtSoundRecorder
import logging
import os
import sys
import time
import threading
import gc
from datetime import datetime
from copy import copy

sys.path.append('./lib')

_conf = Config.get()
_run_event = threading.Event()
_run_event.set()
_sr_tasks = []
threading.currentThread().setName("main")


def setup_logger():
    debug = _conf["DEBUG"] if "DEBUG" in _conf else False
    log_to_file = _conf["LOG_TO_FILE"] if "LOG_TO_FILE" in _conf else False
    log_backup_count = _conf["LOG_BACKUP_COUNT"] if "LOG_BACKUP_COUNT" in _conf else 30

    try:
        # if colorlog installed (pip install colorlog)
        from colorlog import ColoredFormatter
        import logging.config

        logconf = {
            'version': 1,
            'formatters': {
                'colored': {
                    '()': 'colorlog.ColoredFormatter',
                    'format':
                        "%(asctime)-15s %(log_color)s%(levelname)-5s %(process)5d [%(threadName)s] %(message)s"
                }
            },
            'handlers': {
                'stream': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'colored',
                    'level': 'DEBUG' if debug else 'INFO'
                },
            },
            'loggers': {
                '': {
                    'handlers': ["stream"],
                    'level': 'DEBUG' if debug else 'INFO',
                },
            },
        }
        logging.config.dictConfig(logconf)
    except ImportError:
        import logging
        import logging.handlers
        FORMAT = "%(asctime)-15s %(levelname)-5s %(process)5d [%(threadName)s] %(message)s"
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO, format=FORMAT)

    # log to file
    if log_to_file:
        os.makedirs(Config.logdir(), exist_ok=True)
        filehandler = logging.handlers.TimedRotatingFileHandler(os.path.join(
            Config.logdir(), "digiskr.log"), when="midnight", interval=1, backupCount=log_backup_count)
        filehandler.setLevel(logging.DEBUG)
        filehandler.setFormatter(logging.Formatter(
            "%(asctime)-15s %(levelname)-5s %(process)5d [%(threadName)s] %(message)s"))
        logging.getLogger('').addHandler(filehandler)


def setup_kiwistation(station, station_name):
    options = Option(**station)
    options.station = station_name
    options.user = _conf["KIWI_USER"] if "KIWI_USER" in _conf else config.KIWI_USER
    return options


def new_kiwiworker(o, band_hops_str, idx):
    options = copy(o)

    def _extract_band(band_hops_str):
        local = str(band_hops_str).split('|')
        # ['FT8', 'FT4', 'FT8', 'FT8']
        mode_hops = [config.MODES[b[-1]] if b[-1]
                     in config.MODES else "FT8" for b in local]
        # ['20', '30', '40', '60']
        band_hops = [b[:-1] if b[-1]
                     not in [str(n) for n in range(0, 9)] else b for b in local]
        # [14074, 10140, 7074, 5357] in KHz
        freq_hops = [config.BANDS[mode_hops[i]][b]
                     * 1000 for i, b in enumerate(band_hops)]
        return mode_hops, band_hops, freq_hops

    options.band_hops_str = band_hops_str
    options.mode_hops, options.band_hops, options.freq_hops = _extract_band(
        band_hops_str)
    options.idx = idx
    options.timestamp = int(time.time() + os.getpid() + idx) & 0xffffffff
    # tmp dirs preparation
    for i, mode in enumerate(options.mode_hops):
        dir = os.path.join(Config.tmpdir(), options.station,
                           mode, options.band_hops[i])
        if not os.path.isdir(dir):
            os.makedirs(dir, exist_ok=True)
        else:
            os.popen("rm -f %s/*.wav" % dir)

    worker = KiwiWorker(
        target=WsjtSoundRecorder(options),
        name="%s-%s" % (options.station, options.band_hops_str)
    )

    return worker


def cleanup():
    _run_event.clear()
    PskReporter.stop()
    Wsprnet.stop()
    [w.stop() for w in DecoderQueue.instance().workers]
    [r.stop() for r in _sr_tasks]
    [t.join() for t in threading.enumerate() if t is not threading.current_thread()]


def remove_thread(snd, r):
    r.stop()
    if snd.__contains__(r):
        snd.remove(r)
        logging.info("Task #%s removed", r.getName())


def match_schedule(schedules):
    for (ts, schedule) in schedules.items():
        if timespan.match(ts, datetime.now()):
            return schedule

    return None


def main():
    idx = 0
    schedule = match_schedule(_conf["SCHEDULES"])
    if schedule is not None:
        logging.info("current schedule is: %s", schedule)
        for (st, bands) in schedule.items():
            options = setup_kiwistation(_conf["STATIONS"][st], st)
            for band in bands:
                _sr_tasks.append(new_kiwiworker(options, band, idx))
                idx += 1
    try:
        if len(_sr_tasks) == 0:
            logging.warning("No tasks in queue.")
            logging.warning("I\'m out")
            exit(0)
        else:
            DecoderQueue.instance()
            for i, r in enumerate(_sr_tasks):
                r.start()

        # keeper
        while _run_event.is_set():
            time.sleep(1)

            schedule = match_schedule(_conf["SCHEDULES"])
            if schedule is not None:
                # logging.debug('current schedule is: %s', schedule)
                # remove out-of-date tasks
                for r in _sr_tasks:
                    bands = schedule.get(r._options.station)
                    keep_it = False
                    if bands is not None:
                        for band in bands:
                            if band == r._options.band_hops_str:
                                keep_it = True
                                break
                    else:
                        remove_thread(_sr_tasks, r)
                    if not keep_it:
                        remove_thread(_sr_tasks, r)

                # add new tasks
                for (st, bands) in schedule.items():
                    for band in bands:
                        exsit_task = False
                        for r in _sr_tasks:
                            if r.name == "%s-%s" % (st, band):
                                exsit_task = True
                                break
                        if not exsit_task:
                            options = setup_kiwistation(_conf["STATIONS"][st], st)
                            task = new_kiwiworker(options, band, len(_sr_tasks)+1)
                            logging.info("# wait a second to let pre-tasks have a clean quit")
                            time.sleep(1)
                            task.start()
                            _sr_tasks.append(task)
            else:  # no tasks available
                [remove_thread(_sr_tasks, r) for r in _sr_tasks]
                logging.warning("There is no tasks")
                logging.warning("Quit...")
                exit(0)

    except KeyboardInterrupt:
        logging.warning("KeyboardInterrupt: exiting...")
        cleanup()
        logging.info("KeyboardInterrupt: threads successfully closed")
    except Exception:
        cleanup()
        logging.exception("Exception: threads successfully closed")

    logging.debug("gc %s" % gc.garbage)


if __name__ == '__main__':
    setup_logger()
    fail = False
    for e in Config.validateConfig():
        logging.fatal(e)
        fail = True

    if fail:
        exit(1)

    main()
# EOF
