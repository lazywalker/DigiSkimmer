#!/usr/bin/env python
## -*- python -*-
#
# Copyright(c) 2020 BD7MQB Michael Choi <bd7mqb@qq.com>
# This is free software, licensed under the GNU GENERAL PUBLIC LICENSE, Version 2.0
#

from digiskr import config
from digiskr.pskreporter import PskReporter
from digiskr.audio import DecoderQueue
from digiskr.wsjt import FT8Profile, WsjtParser
import logging, os, sys, time, threading
import gc
from datetime import datetime
from copy import copy

sys.path.append('./lib')
from kiwi import KiwiWorker
from digiskr import SoundRecorder, Option, Config
import timespan

conf = Config.get()
_run_event = threading.Event()
_run_event.set()
threading.currentThread().setName('main')
_sr_tasks = []

def setup_logger():
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
                    'level': 'DEBUG'
                },
            },
            'loggers': {
                '': {
                    'handlers': ['stream'],
                    'level': 'DEBUG',
                },
            },
        }
        logging.config.dictConfig(logconf)
    except ImportError:
        import logging, logging.handlers
        FORMAT = "%(asctime)-15s %(levelname)-5s %(process)5d [%(threadName)s] %(message)s"
        logging.basicConfig(level=logging.DEBUG, format=FORMAT)

    # log to file
    filehandler = logging.handlers.TimedRotatingFileHandler("log/ft8.log", when='d', interval=1, backupCount=7)
    filehandler.setLevel(logging.DEBUG)
    filehandler.suffix = "%Y-%m-%d_%H-%M-%S.log"
    filehandler.setFormatter(logging.Formatter("%(asctime)-15s %(levelname)-5s %(process)5d [%(threadName)s] %(message)s"))
    logging.getLogger('').addHandler(filehandler)


def setup_kiwistation(station, station_name):
    options = Option(**station)
    options.station = station_name
    options.user = config.KIWI_USER
    return options

def new_kiwiworker(o, band, idx):
    options = copy(o)
    options.band = band
    options.idx = idx
    options.timestamp = int(time.time() + os.getpid() + idx) & 0xffffffff
    options.frequency = config.FT8_BANDS[options.band]
    options.dir = os.path.join(conf['PATH'], options.station, str(options.band))
    if not os.path.isdir(options.dir):
        os.makedirs(options.dir, exist_ok=True)
    else:
        os.popen("rm -f %s/*.wav" % options.dir)

    worker = KiwiWorker(
            target=SoundRecorder(conf['PATH'], options, FT8Profile(), WsjtParser(options.callsign, options.grid)),
            name = "%s-%d" %(options.station, band)
        )
    
    return worker

def cleanup():
    _run_event.clear()
    PskReporter.stop()
    [w.stop() for w in DecoderQueue.instance().workers]
    [r.stop() for r in _sr_tasks]
    [t.join() for t in threading.enumerate() if t is not threading.currentThread()]

def remove_thread(snd, r):
    r.stop()
    if snd.__contains__(r):
        snd.remove(r)
        logging.info('Task #%s removed', r.getName())

def match_schedule(schedules):
    for (ts, schedule) in schedules.items():
        if timespan.match(ts, datetime.now()):
            return schedule

    return None

def main():
    idx = 0
    schedule = match_schedule(conf['SCHEDULES'])
    if schedule is not None:
        logging.info('current schedule is: %s', schedule)
        for (st, bands) in schedule.items():
            options = setup_kiwistation(conf['STATIONS'][st], st)
            for band in bands:
                _sr_tasks.append(new_kiwiworker(options, band, idx))
                idx += 1
    try:
        if len(_sr_tasks) == 0:
            logging.warning('No tasks in queue.')
            logging.warning('I\'m out')
            exit(0)
        else:
            for i,r in enumerate(_sr_tasks):
                r.start()

        # keeper
        while _run_event.is_set():
            time.sleep(1)

            schedule = match_schedule(conf['SCHEDULES'])
            if schedule is not None:
                # logging.debug('current schedule is: %s', schedule)
                ## remove out-of-date tasks
                for r in _sr_tasks:
                    bands = schedule.get(r._options.station)
                    keep_it = False
                    if bands is not None:
                        for band in bands:
                            if band == r._options.band:
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
                            if r.getName() == '%s-%d' %(st, band):
                                exsit_task = True
                                break
                        if not exsit_task:
                            options = setup_kiwistation(conf['STATIONS'][st], st)
                            task = new_kiwiworker(options, band, len(_sr_tasks)+1)
                            task.start()
                            _sr_tasks.append(task)
            else: #no tasks available
                [remove_thread(_sr_tasks, r) for r in _sr_tasks]
                logging.warning('There is no tasks')
                logging.warning('I\'m waiting...')


    except KeyboardInterrupt:
        logging.warning("KeyboardInterrupt: exiting...")
        cleanup()
        logging.info("KeyboardInterrupt: threads successfully closed")
    except Exception:
        cleanup()
        logging.exception("Exception: threads successfully closed")

    logging.debug('gc %s' % gc.garbage)

if __name__ == '__main__':
    setup_logger()
    main()
# EOF
