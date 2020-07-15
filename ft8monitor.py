#!/usr/bin/env python
## -*- python -*-

import array, logging, os, struct, sys, time, datetime, copy, threading
import gc
import math
import numpy as np
from copy import copy
from traceback import print_exc
from optparse import OptionParser
from optparse import OptionGroup

sys.path.append('./lib')
from kiwi import KiwiSDRStream, KiwiWorker
import timespan
import config

HAS_RESAMPLER = True
VERSION = '0.1'
KIWI_USER = "ft8-monitor_%s" % VERSION
FT8_BANDS = {160:1840, 80:3573, 60:5357, 40:7074, 30:10136, 20:14074, 17:18100, 15:21074, 12:24915, 10:28074}

try:
    ## if available use libsamplerate for resampling
    from samplerate import Resampler
except ImportError:
    ## otherwise linear interpolation is used
    HAS_RESAMPLER = False

def _write_wav_header(fp, filesize, samplerate, num_channels):
    fp.write(struct.pack('<4sI4s', b'RIFF', filesize - 8, b'WAVE'))
    bits_per_sample = 16
    byte_rate       = samplerate * num_channels * bits_per_sample // 8
    block_align     = num_channels * bits_per_sample // 8
    fp.write(struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, num_channels, int(samplerate+0.5), byte_rate, block_align, bits_per_sample))
    fp.write(struct.pack('<4sI', b'data', filesize - 12 - 8 - 16 - 8))

class KiwiSoundRecorder(KiwiSDRStream):
    def __init__(self, options):
        super(KiwiSoundRecorder, self).__init__()
        self._options = options
        self._type = 'SND'
        freq = options.frequency
        #logging.info("%s:%s freq=%d" % (options.server_host, options.server_port, freq))
        self._freq = freq
        self._start_ts = None
        self._start_time = None
        self._squelch = None
        self._num_channels = 2 if options.modulation == 'iq' else 1
        self._resampler = None

    def _setup_rx_params(self):
        if self._options.no_api:
            if self._options.user != 'kiwirecorder.py':
                self.set_name(self._options.user)
            return
        self.set_name(self._options.user)
        mod    = self._options.modulation
        lp_cut = self._options.lp_cut
        hp_cut = self._options.hp_cut
        if mod == 'am':
            # For AM, ignore the low pass filter cutoff
            lp_cut = -hp_cut if hp_cut is not None else hp_cut
        self.set_mod(mod, lp_cut, hp_cut, self._freq)
        if self._options.agc_gain != None:
            self.set_agc(on=False, gain=self._options.agc_gain)
        else:
            self.set_agc(on=True)
        if self._options.compression is False:
            self._set_snd_comp(False)
        if self._options.nb is True:
            gate = self._options.nb_gate
            if gate < 100 or gate > 5000:
                gate = 100
            thresh = self._options.nb_thresh
            if thresh < 0 or thresh > 100:
                thresh = 50
            self.set_noise_blanker(gate, thresh)
        self._output_sample_rate = self._sample_rate
        if self._options.resample > 0:
            self._output_sample_rate = self._options.resample
            self._ratio = float(self._output_sample_rate)/self._sample_rate
            logging.info('resampling from %g to %d Hz (ratio=%f)' % (self._sample_rate, self._options.resample, self._ratio))
            if not HAS_RESAMPLER:
                logging.info("libsamplerate not available: linear interpolation is used for low-quality resampling. "
                             "(pip install samplerate)")

    def _process_audio_samples(self, seq, samples, rssi):
        if self._options.quiet is False:
            sys.stdout.write('\rBlock: %08x, RSSI: %6.1f\r' % (seq, rssi))
            sys.stdout.flush()

        if self._options.resample > 0:
            if HAS_RESAMPLER:
                ## libsamplerate resampling
                if self._resampler is None:
                    self._resampler = Resampler(converter_type='sinc_best')
                samples = np.round(self._resampler.process(samples, ratio=self._ratio)).astype(np.int16)
            else:
                ## resampling by linear interpolation
                n  = len(samples)
                xa = np.arange(round(n*self._ratio))/self._ratio
                xp = np.arange(n)
                samples = np.round(np.interp(xa,xp,samples)).astype(np.int16)

        self._write_samples(samples, {})

    def _get_output_filename(self):
        if self._options.test_mode:
            return os.devnull
        station = '' if self._options.station is None else '_'+ self._options.station

        if self._options.filename != '':
            filename = '%s%s.wav' % (self._options.filename, station)
        else:
            ts  = time.strftime('%Y%m%dT%H%M%SZ', self._start_ts)
            filename = '%s_%d%s_%s.wav' % (ts, int(self._freq * 1000), station, self._options.modulation)
        if self._options.dir is not None:
            filename = '%s/%s' % (self._options.dir, filename)
        return filename

    def _update_wav_header(self):
        with open(self._get_output_filename(), 'r+b') as fp:
            fp.seek(0, os.SEEK_END)
            filesize = fp.tell()
            fp.seek(0, os.SEEK_SET)

            # fp.tell() sometimes returns zero. _write_wav_header writes filesize - 8
            if filesize >= 8:
                _write_wav_header(fp, filesize, int(self._output_sample_rate), self._num_channels)

    def _write_samples(self, samples, *args):
        """Output to a file on the disk."""
        now = time.gmtime()
        sec_of_day = lambda x: 3600*x.tm_hour + 60*x.tm_min + x.tm_sec
        dt_reached = self._options.dt != 0 and self._start_ts is not None and sec_of_day(now)//self._options.dt != sec_of_day(self._start_ts)//self._options.dt
        
        if self._start_ts is None or (self._options.filename == '' and dt_reached):
            if self._start_ts is not None:
                # Call jt9 to process decoding
                cmd = "timeout 30 nice jt9 -8 -e {dir} -a {dir} -t {dir} {filename} | awk -v date={date} 'gsub(\"000000\", date)' | awk -v freq={freq} 'gsub(\"~\",freq)' >> {output} && echo \"Decoding Band {band}m\" >> {output} &&  rm {filename}".format(
                    dir = self._options.dir,
                    filename = self._get_output_filename(),
                    date = datetime.datetime.now().strftime('%H%M%S'),
                    band = self._options.band,
                    freq = self._freq,
                    output = os.path.join(config.PATH, self._options.station, "decode-ft8.log")
                )
                logging.info("decoding band %dm", self._options.band)
                os.popen(cmd)
            
            self._start_ts = now
            self._start_time = time.time()
            # Write a static WAV header
            with open(self._get_output_filename(), 'wb') as fp:
                _write_wav_header(fp, 100, int(self._output_sample_rate), self._num_channels)
        with open(self._get_output_filename(), 'ab') as fp:
            # TODO: something better than that
            samples.tofile(fp)
        self._update_wav_header()

class Option:
    dir = config.PATH
    def __init__(self, **entries):
        default = {
            'filename': '',
            'quiet': False,
            'dir': None,
            'tlimit': None,
            'dt': 0,
            'connect_retries': 0, 
            'connect_timeout': 15, 
            'socket_timeout': 10, 
            'ADC_OV': False, 
            'tstamp': False, 
            'stats': True, 
            'no_api': False, 
            'modulation': 'usb', 
            'compression': True, 
            'lp_cut': 0.0, 
            'hp_cut': 3000.0, 
            'resample': 0, 
            'agc_gain': None, 
            'nb': False, 
            'nb_gate': 100, 
            'nb_thresh': 50, 
            'test_mode': False, 
            'sound': False, 
            'S_meter': -1, 
            'sdt': 0, 
            'raw': False, 
            'status': 0, 
            'timestamp': int(time.time() + os.getpid()) & 0xffffffff,
            'idx' : 0
        }
        self.__dict__.update(default)
        self.__dict__.update(entries)

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

    worker = KiwiWorker(args=(KiwiSoundRecorder(options), options))
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

    # config.STATIONS = {
    #     'czsdr': {
    #         'server_host': 'cz.kiwisdr.go1982.com', 
    #         'server_port': 8073,
    #         'password': 'letmeiN',
    #         'tlimit_password': 'letmeiN',
    #         'callsign': 'BD7MQB-2',
    #         'grid': 'OM88co',
    #     },
    #     'szsdr': {
    #         'server_host': 'base.go1982.com', 
    #         'server_port': 8074,
    #         # 'server_host': 'radiopi.local', 
    #         # 'server_port': 8073,
    #         'password': 'letmeiN',
    #         'tlimit_password': 'letmeiN',
    #         'callsign': 'BD7MQB',
    #         'grid': 'OL72an',
    #     },
    # }
    # config.SCHEDULES = {
    #     # '*': {'szsdr': [20,30], 'czsdr': [20,30]},
    #     # '14:00-17:08': {'szsdr': [40, 20], 'czsdr': [40]},
    #     # '20:00-20:51': {'szsdr': [20, 60]},
    #     # '20:51-22:00': {'szsdr': [40, 30, 20], 'czsdr': [20, 40]},
    #     # '*': {'szsdr': [10, 12, 15, 17, 20, 30, 40, 60, 80, 160]},
    #     '21:00-08:00': {'szsdr': [10, 12, 15, 17, 20, 30, 40, 60, 80, 160], 'czsdr': [20, 30, 40, 60, 80, 160]},
    #     '08:00-14:30': {'szsdr': [10, 12, 15, 17, 20, 30, 40, 60, 80, 160], 'czsdr': [10, 12, 15, 17, 20, 30]},
    #     '14:30-21:00': {'szsdr': [10, 12, 15, 17, 20, 30, 40, 60, 80, 160], 'czsdr': [10, 15, 17, 20, 30, 40]},
    # }

    snd_recorders = []
    idx = 0
    schedule = match_schedule(config.SCHEDULES)
    if schedule is not None:
        logging.info('current schedule is: %s', schedule)
        for (st, bands) in schedule.items():
            options = initKiwiStation(config.STATIONS[st], st)
            for band in bands:
                snd_recorders.append(newKiwiWorker(options, band, idx))
                idx += 1
    try:
        if len(snd_recorders) == 0:
            logging.warning('No tasks in queue.')
            logging.warning('I\'m out')
            exit()
        else:
            for k,v in config.STATIONS.items():
                pskr(k, v['callsign'], v['grid'])
            for i,r in enumerate(snd_recorders):
                r.start()

        # keeper
        while run_event.is_set():
            time.sleep(1)

            schedule = match_schedule(config.SCHEDULES)
            if schedule is not None:
                logging.debug('current schedule is: %s', schedule)
                ## remove out-of-date tasks
                for r in snd_recorders:
                    bands = schedule.get(r._options.station)
                    keep_it = False
                    if bands is not None:
                        for band in bands:
                            if band == r._options.band:
                                keep_it = True
                                break
                    else:
                        remove_thread(snd_recorders, r)
                    if not keep_it:
                        remove_thread(snd_recorders, r)
                
                # add new tasks
                for (st, bands) in schedule.items():
                    for band in bands:
                        exsit_task = False
                        for r in snd_recorders:
                            if r.getName() == '%s-%d' %(st, band):
                                exsit_task = True
                                break
                        if not exsit_task:
                            options = initKiwiStation(config.STATIONS[st], st)
                            task = newKiwiWorker(options, band, len(snd_recorders)+1)
                            task.start()
                            snd_recorders.append(task)
            else: #no tasks available
                [remove_thread(snd_recorders, r) for r in snd_recorders]
                logging.warning('There is no tasks')
                logging.warning('I\'m waiting...')


    except KeyboardInterrupt:
        run_event.clear()
        join_threads(snd_recorders)
        print("KeyboardInterrupt: threads successfully closed")
    except Exception:
        print_exc()
        run_event.clear()
        join_threads(snd_recorders)
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
