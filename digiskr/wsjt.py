from datetime import datetime
from digiskr.wsprnet import Wsprnet
from digiskr.parser import LineParser
import re, time
from digiskr.pskreporter import PskReporter
from digiskr.base import AudioDecoderProfile
from digiskr.config import Config
from abc import ABC, ABCMeta, abstractmethod

import logging

class WsjtProfile(AudioDecoderProfile, metaclass=ABCMeta):
    def decoding_depth(self, mode):
        conf = Config.get()
        if "WSJTX" in conf:
            conf = conf["WSJTX"]
            # mode-specific setting?
            if "decoding_depth_modes" in conf and mode in conf["decoding_depth_modes"]:
                return conf["decoding_depth_modes"][mode]
            # return global default
            if "decoding_depth_global" in conf:
                return conf["decoding_depth_global"]
        
        # default when no setting is provided
        return 3

    @staticmethod
    def get(mode: str):
        if mode == "FT8":
            return FT8Profile()
        elif mode == "FT4":
            return FT4Profile()
        elif mode == "WSPR":
            return WsprProfile()
        else:
            raise Exception("invalid mode!")
    

class FT8Profile(WsjtProfile):
    def getMode(self):
        return "FT8"
    
    def getInterval(self):
        return 15

    def getFileTimestampFormat(self):
        return "%y%m%d_%H%M%S"

    def decoder_commandline(self, file):
        return ["jt9", "--ft8", "-d", str(self.decoding_depth("ft8")), file]


class FT4Profile(WsjtProfile):
    def getMode(self):
        return "FT4"

    def getInterval(self):
        return 7.5

    def getFileTimestampFormat(self):
        return "%y%m%d_%H%M%S"

    def decoder_commandline(self, file):
        return ["jt9", "--ft4", "-d", str(self.decoding_depth("ft4")), file]


class WsprProfile(WsjtProfile):
    def getMode(self):
        return "WSPR"

    def getInterval(self):
        return 120

    def getFileTimestampFormat(self):
        return "%y%m%d_%H%M"

    def decoder_commandline(self, file):
        cmd = ["wsprd"]
        if self.decoding_depth("wspr") > 1:
            cmd += ["-d"]
        cmd += [file]
        return cmd


class JT65Profile(WsjtProfile):
    def getInterval(self):
        return 60

    def getFileTimestampFormat(self):
        return "%Y%m%d %H%M"

    def decoder_commandline(self, file):
        return ["jt9", "--jt65", "-d", str(self.decoding_depth("jt65")), file]


class JT9Profile(WsjtProfile):
    def getInterval(self):
        return 60

    def getFileTimestampFormat(self):
        return "%Y%m%d %H%M"

    def decoder_commandline(self, file):
        return ["jt9", "--jt9", "-d", str(self.decoding_depth("jt9")), file]


class WsjtParser(LineParser):
    modes = {"~": "FT8", "#": "JT65", "@": "JT9", "+": "FT4"}

    def parse(self, messages):
        for data in messages:
            try:
                freq, raw_msg = data
                self.dial_freq = freq
                msg = raw_msg.decode().rstrip()
                # known debug messages we know to skip
                if msg.startswith("<DecodeFinished>"):  # this is what jt9 std output
                    return
                if msg.startswith(" EOF on input file"): # this is what jt9 std output
                    return

                modes = list(WsjtParser.modes.keys())
                if msg[21] in modes or msg[19] in modes:
                    decoder = JT9Decoder()
                else:
                    decoder = WsprDecoder()
                out = decoder.parse(msg, freq)
                logging.info("[%s] %s T%s DB%2.1f DT%2.1f F%2.6f %s : %s %s", 
                    self.getStation(), 
                    out["mode"], 
                    time.strftime("%H%M%S",  time.localtime(out["timestamp"])),
                    out["db"], out["dt"], out["freq"], out["msg"], 
                    out["callsign"] if "callsign" in out else "-", 
                    out["locator"] if "locator" in out else "")
                if "mode" in out:
                    if "callsign" in out and "locator" in out:
                        PskReporter.getSharedInstance(self.getStation()).spot(out)
                        # upload to wsprnet as well
                        if out["mode"] == "WSPR":
                            Wsprnet.getSharedInstance(self.getStation()).spot(out)

            except ValueError:
                logging.exception("error while parsing wsjt message")


class Decoder(ABC):
    def parse_timestamp(self, instring, dateformat):
        ts = datetime.strptime(instring, dateformat)
        return int(
            datetime.combine(datetime.now().date(), ts.time()).timestamp()
        )

    @abstractmethod
    def parse(self, msg, dial_freq):
        pass


class JT9Decoder(Decoder):
    # CQ DX BD7MQB OM92
    locator_pattern = re.compile(".+[A-Z0-9/]+\s([A-Z0-9/]+?)\s([A-R]{2}[0-9]{2})$")
    # HU4FUJ CV1KUS/R R NC08
    locator_pattern2 = re.compile(".+[A-Z0-9/]+\s([A-Z0-9/]+?)\s[A-Z]\s([A-R]{2}[0-9]{2})$")

    def parse(self, msg, dial_freq):
        # ft8 sample
        # '222100 -15 -0.0  508 ~  CQ EA7MJ IM66'
        # '000000 -11  0.2 1000 ~  CQ EU BG4WOM OM92'
        # jt65 sample
        # '2352  -7  0.4 1801 #  R0WAS R2ABM KO85'
        # '0003  -4  0.4 1762 #  CQ R2ABM KO85'

        modes = list(WsjtParser.modes.keys())
        if msg[19] in modes:
            dateformat = "%H%M"
        else:
            dateformat = "%H%M%S"
        timestamp = self.parse_timestamp(msg[0 : len(dateformat)], dateformat)
        msg = msg[len(dateformat) + 1 :]
        modeChar = msg[14:15]
        mode = WsjtParser.modes[modeChar] if modeChar in WsjtParser.modes else "unknown"
        wsjt_msg = msg[17:53].strip()

        result = {
            "timestamp": timestamp,
            "db": float(msg[0:3]),
            "dt": float(msg[4:8]),
            "freq": (dial_freq * 1000 + int(msg[9:13])) / 1e6,
            "mode": mode,
            "msg": wsjt_msg,
        }
        result.update(self.parseMessage(wsjt_msg))
        return result

    def parseMessage(self, msg):
        if msg.startswith("CQ") or len(msg.split(" ")) == 3:
            m = JT9Decoder.locator_pattern.match(msg)
        else:
            m = JT9Decoder.locator_pattern2.match(msg)

        if m is None:
            return {}
        if m.group(2) == "RR73":
            return {"callsign": m.group(1).split("/")[0]}
        return {"callsign": m.group(1).split("/")[0], "locator": m.group(2)}


class WsprDecoder(Decoder):
    wspr_splitter_pattern = re.compile("([A-Z0-9]*)\s([A-R]{2}[0-9]{2})\s([0-9]+)")

    def parse(self, msg, dial_freq):
        # wspr sample
        # '2600 -24  0.4   0.001492 -1  G8AXA JO01 33'
        # '0052 -29  2.6   0.001486  0  G02CWT IO92 23'
        wsjt_msg = msg[29:].strip()

        # TODO: No idea what sync_quality used for but we need to add this field to bypass the upload check,
        # it seems to useless because the static files downloaded from wsprnet.org doesn't contain this field.
        # i don't want to read it from wspr_spots.txt so i simply pick a random value :)
        result = {
            "timestamp": self.parse_timestamp(msg[0:4], "%H%M"),
            "db": float(msg[5:8]),
            "dt": float(msg[9:13]),
            "freq": (dial_freq * 1000 + int(float(msg[14:24]) * 1e6)) / 1e6,
            "drift": int(msg[25:28]),
            "mode": "WSPR",
            "sync_quality": 0.7,
            "msg": wsjt_msg,
        }
        result.update(self.parseMessage(wsjt_msg))
        return result

    def parseMessage(self, msg):
        m = WsprDecoder.wspr_splitter_pattern.match(msg)
        if m is None:
            return {}
        # TODO: handle msg type "<G0EKQ>        IO83PI 37"
        return {"callsign": m.group(1), "locator": m.group(2), "watt": int(m.group(3))}
