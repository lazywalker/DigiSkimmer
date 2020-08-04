from digiskr.wsjt import WsjtParser, WsjtProfile
from digiskr.config import Config
from digiskr.base import BaseSoundRecorder, DecoderQueue, Option, QueueJob
import subprocess
import logging, os, time
from queue import Full


class WsjtSoundRecorder(BaseSoundRecorder):
    def __init__(self, options: Option):
        self._profile= WsjtProfile.get(options.mode_hops[0])
        self._parser = WsjtParser(options.station)
        
        options.dt = self._profile.getInterval()
        super(WsjtSoundRecorder, self).__init__(options)

    def on_bandhop(self):
        ## if we are hitting a new minute
        if len(self._options.band_hops) > 1 and self.band_hop_minute != time.localtime().tm_min:
            self.band_hop_minute = time.localtime().tm_min
            for i, f in enumerate(self._options.freq_hops):
                if f == self._freq:
                    next = i+1 if i < len(self._options.freq_hops)-1 else 0
                    self._freq = self._options.freq_hops[next]
                    self._band = self._options.band_hops[next]
                    self._profile = WsjtProfile.get(self._options.mode_hops[next])
                    self._options.dt = self._profile.getInterval()
                    break

            # switching to next frequency and mode
            logging.warning("switching to %s-%sm", self._profile.getMode(), self._band)
            self.set_mod(self._options.modulation, self._options.lp_cut, self._options.hp_cut, self._freq)


    def pre_decode(self):
        filename = self._get_output_filename()
        job = QueueJob(self, filename, self._freq)
        try:
            # logging.debug("put a new job into queue %s", filename)
            DecoderQueue.instance().put(job)
        except Full:
            logging.error("decoding queue overflow; dropping one file")
            job.unlink()

    def decode(self, job: QueueJob):
        logging.debug("processing file %s", job.file)
        file = os.path.realpath(job.file)
        decoder = subprocess.Popen(
            ["nice", "-n", "10"] + self._profile.decoder_commandline(file),
            stdout=subprocess.PIPE,
            cwd=os.path.dirname(file),
            close_fds=True,
            )
        
        # No need for now, since WSJT-X read time from filename
        # filename = os.path.basename(job.file)
        # file_t = time.strptime(filename.split('-')[-1][:-4], self._profile.getFileTimestampFormat())   # Get time from filename like 200803_152201.wav
        # receive_ts = time.strftime(self._profile.getLineTimestampFormat(), file_t)
        messages = []
        for line in decoder.stdout:
            # line = line.replace("000000".encode("utf-8"), receive_ts.encode("utf-8")) # No need for now, since WSJT-X read time from filename
            logging.log(logging.DEBUG, line)
            messages.append((job.freq, line))
        
        # set grid & antenna information from kiwi station, if we can't found them at config
        if not "grid" in Config.get()["STATIONS"][self._options.station]:
            Config.get()["STATIONS"][self._options.station]["grid"] = self._rx_grid
        if not "antenna" in Config.get()["STATIONS"][self._options.station]:
            Config.get()["STATIONS"][self._options.station]["antenna"] = self._rx_antenna
        
        ## parse raw messages
        self._parser.parse(messages)
        
        try:
            rc = decoder.wait(timeout=10)
            if rc != 0:
                logging.warning("decoder return code: %i", rc)
        except subprocess.TimeoutExpired:
            logging.warning("subprocess (pid=%i}) did not terminate correctly; sending kill signal.", decoder.pid)
            decoder.kill()
