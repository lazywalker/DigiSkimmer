#!/usr/bin/env python
## -*- python -*-
#
# Copyright(c) 2020 BD7MQB Michael Choi <bd7mqb@qq.com>
# This is free software, licensed under the GNU GENERAL PUBLIC LICENSE, Version 2.0
#

import array, logging, os, sys, time, datetime, copy, threading
import gc
from copy import copy
from traceback import print_exc
from optparse import OptionParser
from optparse import OptionGroup

sys.path.append('./lib')
from kiwi import KiwiWorker
from digiskr import SoundRecorder, Option
import timespan
import config

VERSION = '0.1'
KIWI_USER = "ft8-monitor_%s" % VERSION
FT8_BANDS = {160:1840, 80:3573, 60:5357, 40:7074, 30:10136, 20:14074, 17:18100, 15:21074, 12:24915, 10:28074, 6:50313}


def initKiwiStation(station, station_name):
    options = Option(**station)
    options.dt = 15 ## 15 seconds per span
    options.station = station_name
    options.user = KIWI_USER
    return options

def newKiwiWorker(o, band, idx):
    options = copy(o)
    options.band = band
    options.idx = idx
    options.timestamp = int(time.time() + os.getpid() + idx) & 0xffffffff
    options.frequency = FT8_BANDS[options.band]
    options.dir = os.path.join(config.PATH, options.station, str(options.band))
    if not os.path.isdir(options.dir):
        os.makedirs(options.dir, exist_ok=True)
    else:
        os.popen("rm -f %s/*.wav" % options.dir)

    worker = KiwiWorker(args=(SoundRecorder(config.PATH, options), options))
    worker.setName('%s-%d' %(options.station, band))
    
    return worker

def join_threads(snd):
    [r.stop() for r in snd]
    [t.join() for t in threading.enumerate() if t is not threading.currentThread()]

def remove_thread(snd, r):
    r.stop()
    if snd.__contains__(r):
        snd.remove(r)
        logging.info('Task #%s removed', r.getName())

def match_schedule(schedules):
    for (ts, schedule) in schedules.items():
        if timespan.match(ts, datetime.datetime.now()):
            return schedule

    return None

def pskr(station, callsign, grid):
    logfile = os.path.join(config.PATH, station, 'decode-ft8.log')
    # make sure that logfile is available
    os.makedirs(os.path.join(config.PATH, station), exist_ok=True)
    os.popen('touch %s' % logfile)
    cmd = './pskr.pl %s %s %s' %(callsign, grid, logfile)
    os.popen(cmd)
    logging.info('starting pskr daemon: %s' %cmd)

def main():
    run_event = threading.Event()
    run_event.set()
    threading.currentThread().setName('main')

    sr_tasks = []
    idx = 0
    schedule = match_schedule(config.SCHEDULES)
    if schedule is not None:
        logging.info('current schedule is: %s', schedule)
        for (st, bands) in schedule.items():
            options = initKiwiStation(config.STATIONS[st], st)
            for band in bands:
                sr_tasks.append(newKiwiWorker(options, band, idx))
                idx += 1
    try:
        if len(sr_tasks) == 0:
            logging.warning('No tasks in queue.')
            logging.warning('I\'m out')
            exit()
        else:
            for k,v in config.STATIONS.items():
                pskr(k, v['callsign'], v['grid'])
            for i,r in enumerate(sr_tasks):
                r.start()

        # keeper
        while run_event.is_set():
            time.sleep(1)

            schedule = match_schedule(config.SCHEDULES)
            if schedule is not None:
                logging.debug('current schedule is: %s', schedule)
                ## remove out-of-date tasks
                for r in sr_tasks:
                    bands = schedule.get(r._options.station)
                    keep_it = False
                    if bands is not None:
                        for band in bands:
                            if band == r._options.band:
                                keep_it = True
                                break
                    else:
                        remove_thread(sr_tasks, r)
                    if not keep_it:
                        remove_thread(sr_tasks, r)
                
                # add new tasks
                for (st, bands) in schedule.items():
                    for band in bands:
                        exsit_task = False
                        for r in sr_tasks:
                            if r.getName() == '%s-%d' %(st, band):
                                exsit_task = True
                                break
                        if not exsit_task:
                            options = initKiwiStation(config.STATIONS[st], st)
                            task = newKiwiWorker(options, band, len(sr_tasks)+1)
                            task.start()
                            sr_tasks.append(task)
            else: #no tasks available
                [remove_thread(sr_tasks, r) for r in sr_tasks]
                logging.warning('There is no tasks')
                logging.warning('I\'m waiting...')


    except KeyboardInterrupt:
        run_event.clear()
        join_threads(sr_tasks)
        print("KeyboardInterrupt: threads successfully closed")
    except Exception:
        print_exc()
        run_event.clear()
        join_threads(sr_tasks)
        print("Exception: threads successfully closed")

    logging.debug('gc %s' % gc.garbage)

if __name__ == '__main__':
    #import faulthandler
    #faulthandler.enable()
    FORMAT = '%(asctime)-15s pid %(process)5d [%(threadName)s] %(message)s'
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    # gc.set_debug(gc.DEBUG_SAVEALL | gc.DEBUG_LEAK | gc.DEBUG_UNCOLLECTABLE)
    main()
# EOF
