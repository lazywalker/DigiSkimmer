from digiskr.parser import LineParser
import threading
import logging, os, time, sys, struct
import numpy as np
from queue import Queue, Full, Empty
from abc import ABC, ABCMeta, abstractmethod
from digiskr.config import Config

from kiwi.client import KiwiSDRStream

HAS_RESAMPLER = True
try:
    ## if available use libsamplerate for resampling
    from samplerate import Resampler
except ImportError:
    ## otherwise linear interpolation is used
    HAS_RESAMPLER = False

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

class BaseSoundRecorder(KiwiSDRStream, metaclass=ABCMeta):
    def __init__(self, options: Option, profile: AudioDecoderProfile, parser: LineParser):
        super(BaseSoundRecorder, self).__init__()
        self._options = options
        self._options.dt = profile.getInterval()
        self._type = 'SND'
        self._band = options.band
        self._freq = options.frequency
        self._start_ts = None
        self._start_time = None
        self._squelch = None
        self._num_channels = 2 if options.modulation == 'iq' else 1
        self._resampler = None
        self._profile = profile
        self._parser = parser

        self.band_hop_minute = time.localtime().tm_min
        self.tmp_dir = Config.get()['PATH']

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
            ts  = time.strftime(self._profile.getFileTimestampFormat(), self._start_ts)
            filename = '%s_%d%s_%s.wav' % (ts, int(self._freq * 1000), station, self._options.modulation)
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
        
        if self._start_ts is None or (self._options.filename == '' and dt_reached):
            ## new decoding job
            if self._start_ts is not None:
                self.pre_decode()

                ## handle band hops
                self._hop()

            self._start_ts = now
            self._start_time = time.time()
            # Write a static WAV header
            with open(self._get_output_filename(), 'wb') as fp:
                self._write_wav_header(fp, 100, int(self._output_sample_rate), self._num_channels)
        with open(self._get_output_filename(), 'ab') as fp:
            # TODO: something better than that
            samples.tofile(fp)
        self._update_wav_header()

    def _hop(self):
        ## if we are hitting a new minute
        if len(self._options.band_hops) > 1 and self.band_hop_minute != time.localtime().tm_min:
            self.band_hop_minute = time.localtime().tm_min
            for i, f in enumerate(self._options.freq_hops):
                if f == self._freq:
                    next = i+1 if i < len(self._options.freq_hops)-1 else 0
                    self._freq = self._options.freq_hops[next]
                    self._band = self._options.band_hops[next]
                    break

            # switching to next frequency
            logging.warning("switching to %sm", self._band)
            # self._send_message('SET freq=%.3f' % self._freq)
            self.set_mod(self._options.modulation, self._options.lp_cut, self._options.hp_cut, self._freq)

    @abstractmethod
    def pre_decode(self):
        pass

    @abstractmethod
    def decode(self, job: QueueJob):
        pass

