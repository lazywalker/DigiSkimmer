from digiskr.config import Config
from digiskr.base import BaseSoundRecorder, DecoderQueue, Option, AudioDecoderProfile, QueueJob
from digiskr.parser import LineParser
import subprocess
import logging, os, time
from queue import Full


class WsjtSoundRecorder(BaseSoundRecorder):
    def __init__(self, options: Option, profile: AudioDecoderProfile, parser: LineParser):
        super(WsjtSoundRecorder, self).__init__(options, profile, parser)

    def pre_decode(self):
        filename = self._get_output_filename()
        job = QueueJob(self, filename, self._freq)
        try:
            logging.debug("put a new job into queue %s", filename)
            DecoderQueue.instance().put(job)
        except Full:
            logging.error("decoding queue overflow; dropping one file")
            job.unlink()

    def decode(self, job: QueueJob):
        logging.info("processing file %s", job.file)
        file = os.path.realpath(job.file)
        decoder = subprocess.Popen(
            ["nice", "-n", "10"] + self._profile.decoder_commandline(file),
            stdout=subprocess.PIPE,
            cwd=os.path.dirname(file),
            close_fds=True,
            )
        
        messages = []
        filename = os.path.basename(job.file)
        file_t = time.strptime(filename.split('_')[0], self._profile.getFileTimestampFormat())
        receive_ts = time.strftime(self._profile.getLineTimestampFormat(), file_t)

        for line in decoder.stdout:
            line = line.replace("000000".encode("utf-8"), receive_ts.encode("utf-8"))
            logging.log(logging.NOTSET, line)
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
