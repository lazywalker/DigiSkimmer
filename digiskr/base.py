import math
import random
import threading
import logging, os, time, sys, struct
from queue import Queue, Full, Empty
from abc import ABC, ABCMeta, abstractmethod

from digiskr import config
from digiskr.config import Config

from kiwi.client import KiwiSDRStream

class QueueJob(object):
    def __init__(self, decoder, file, freq):
        super().__init__()
        self.decoder = decoder
        self.file = file
        self.freq = freq

    def run(self):
        self.decoder.decode(self)

    def unlink(self):
        try:
            # logging.debug("deleting file %s" % self.file)
            os.unlink(self.file)
            pass
        except FileNotFoundError:
            logging.warning("file %s not found", self.file)
            pass


class QueueWorker(threading.Thread):
    def __init__(self, queue, name):
        self.queue = queue
        self.run_event = threading.Event()
        super().__init__(name = name)

    def start(self):
        logging.info('QueueWorker %s started' % self.getName())

        self.run_event.set()
        super().start()

    def run(self) -> None:
        while self.run_event.is_set():
            job = None
            try:
                job = self.queue.get(timeout=0.1)
                job.run()
            except Empty:
                pass
            except Exception:
                logging.exception("failed to decode job")
                self.queue.onError()
            finally:
                if job is not None:
                    job.unlink()
                    self.queue.task_done()
            
    def stop(self):
        self.run_event.clear()
        logging.info("QueueWorker %s stop." % self.getName())


class DecoderQueue(Queue):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def instance():
        with DecoderQueue.creationLock:
            if DecoderQueue.sharedInstance is None:
                conf = Config.get()
                maxsize, workers = 10, 3
                if "DECODER_QUEUE" in conf:
                    conf = conf["DECODER_QUEUE"]
                    maxsize = conf["maxsize"] if "maxsize" in conf else maxsize
                    workers = conf["workers"] if "workers" in conf else workers
                   
                DecoderQueue.sharedInstance = DecoderQueue(maxsize, workers)
        return DecoderQueue.sharedInstance

    def __init__(self, maxsize, workers):
        super().__init__(maxsize)
        self.workers = [self.newWorker(i) for i in range(0, workers)]

    def put(self, item, **kwars):
        try:
            super(DecoderQueue, self).put(item, block=False)
        except Full:
            raise

    def get(self, **kwargs):
        out = super(DecoderQueue, self).get(**kwargs)
        return out

    def newWorker(self, i):
        worker = QueueWorker(self, "QW-%d" % i)
        worker.start()
        return worker

    def onError(self):
        pass


class AudioDecoderProfile(ABC):
    @abstractmethod
    def getMode(self):
        pass

    @abstractmethod
    def getInterval(self):
        pass

    @abstractmethod
    def getFileTimestampFormat(self):
        pass

    @abstractmethod
    def getLineTimestampFormat(self):
        pass
    
    @abstractmethod
    def decoder_commandline(self, file):
        pass

class Option:
    def __init__(self, **entries):
        default = {
            'filename': '',
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

class BaseSoundRecorder(KiwiSDRStream, metaclass=ABCMeta):
    def __init__(self, options: Option):
        super(BaseSoundRecorder, self).__init__()
        self._options = options
        self._type = 'SND'
        self._band = options.band_hops[0]
        self._freq = options.freq_hops[0]
        self._start_ts = None
        self._start_time = None
        self._squelch = None
        self._num_channels = 2 if options.modulation == 'iq' else 1

        self.band_hop_ts = time.time()

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

    def _process_audio_samples(self, seq, samples, rssi):
        self._write_samples(samples, {})

    def _get_output_filename(self):
        if self._options.test_mode:
            return os.devnull

        if self._options.filename != '':
            filename = '%s-%s.wav' % (self._options.filename, self._profile.getMode())
        else:
            ts  = time.strftime(self._profile.getFileTimestampFormat(), self._start_ts)
            filename = '%s.wav' % ts
        if self._options.dir is not None:
            filename = '%s/%s' % (self._options.dir, filename)
        return filename
            
    def _write_wav_header(self, fp, filesize, samplerate, num_channels):
        fp.write(struct.pack('<4sI4s', b'RIFF', filesize - 8, b'WAVE'))
        bits_per_sample = 16
        byte_rate       = samplerate * num_channels * bits_per_sample // 8
        block_align     = num_channels * bits_per_sample // 8
        fp.write(struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, num_channels, int(samplerate+0.5), byte_rate, block_align, bits_per_sample))
        fp.write(struct.pack('<4sI', b'data', filesize - 12 - 8 - 16 - 8))
        
    def _update_wav_header(self):
        with open(self._get_output_filename(), 'r+b') as fp:
            fp.seek(0, os.SEEK_END)
            filesize = fp.tell()
            fp.seek(0, os.SEEK_SET)

            # fp.tell() sometimes returns zero. _write_wav_header writes filesize - 8
            if filesize >= 8:
                self._write_wav_header(fp, filesize, int(self._output_sample_rate), self._num_channels)

    def _write_samples(self, samples, *args):
        """Output to a file on the disk."""
        now = time.localtime()
        sec_of_day = lambda x: 3600*x.tm_hour + 60*x.tm_min + x.tm_sec
        dt_reached = self._options.dt != 0 and self._start_ts is not None and sec_of_day(now)//self._options.dt != sec_of_day(self._start_ts)//self._options.dt
        if self._profile.getMode() == "WSPR":
            time_to_wait = (60 - now.tm_sec) % self._profile.getInterval() + (60 if now.tm_min %2 == 0 else 0) # odd minute
        else:
            time_to_wait = (60 - now.tm_sec) % self._profile.getInterval()

        # print out progress bar at the buttom of screen
        self._print_status(time_to_wait)

        # first time or timespan is reached
        if self._start_ts is None or (self._options.filename == '' and dt_reached):
            # ignore first time (empty file)
            if self._start_ts is not None:
                ## new decoding job
                self.pre_decode()
                ## handle band hops
                self.on_bandhop()

            self._start_ts = now
            self._start_time = time.time()
            # Write a static WAV header
            with open(self._get_output_filename(), 'wb') as fp:
                self._write_wav_header(fp, 100, int(self._output_sample_rate), self._num_channels)
        with open(self._get_output_filename(), 'ab') as fp:
            # TODO: something better than that
            samples.tofile(fp)
        self._update_wav_header()

    def _print_status(self, time_to_wait):
        if self._profile.getMode() == "FT4":    # ft4 takes second position of status bar
            pos = 1
        elif self._profile.getMode() == "WSPR":    # wspr takes thrid position of status bar
            pos = 2
        else:
            pos = 0
        tab = "".join(["\t" for _ in range(0,3*pos)])
            
        bar = tab + "".join([
                self._profile.getMode(),
                ":[",
                "".join(["#" for _ in range(0, math.floor((self._profile.getInterval()-time_to_wait)*10/self._profile.getInterval()))]),
                "".join(["." for _ in range(0, math.ceil(time_to_wait*10/self._profile.getInterval()))]),
                "]"
            ])
        loading = ["-", "\\", "|", "/"][int(random.uniform(0, 4))]
        sys.stdout.write("\r %s[%2.2d] %s\r" % (loading, time.localtime().tm_sec, bar))
        sys.stdout.flush()

    @abstractmethod
    def on_bandhop(self):
        pass

    @abstractmethod
    def pre_decode(self):
        pass

    @abstractmethod
    def decode(self, job: QueueJob):
        pass

