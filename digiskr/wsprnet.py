import os
import logging
import threading
from threading import Thread
import time
import random
from functools import reduce
from operator import and_
from digiskr.config import Config

import requests

class Wsprnet(object):
    sharedInstance = {}
    creationLock = threading.Lock()
    # avoid the two minute boundaries 
    interval = 45
    supportedModes = ["WSPR"]

    @staticmethod
    def getSharedInstance(station: str):
        with Wsprnet.creationLock:
            if Wsprnet.sharedInstance.get(station) is None:
                Wsprnet.sharedInstance[station] = Wsprnet(station)
        return Wsprnet.sharedInstance[station]

    @staticmethod
    def stop():
        [psk.cancelTimer() for psk in Wsprnet.sharedInstance.values()]

    def __init__(self, station: str):
        self.spots = []
        self.spotLock = threading.Lock()
        self.station = station
        self.timer = None

        # prepare tmpdir for uploader
        self.tmpdir = os.path.join(Config.tmpdir(), station, "WSPR", "wsprnet.uploader")
        os.makedirs(self.tmpdir, exist_ok=True)

        self.uploader = Uploader(station, self.tmpdir)

    def scheduleNextUpload(self):
        if self.timer:
            return
        delay = Wsprnet.interval + random.uniform(0, 15)
        logging.info("scheduling next wsprnet upload in %3.2f seconds", delay)
        self.timer = threading.Timer(delay, self.upload)
        self.timer.setName("wsprnet.uploader-%s" % self.station)
        self.timer.start()

    def spotEquals(self, s1, s2):
        keys = ["callsign", "timestamp",
                "locator", "db", "freq", "mode", "msg"]

        return reduce(and_, map(lambda key: s1[key] == s2[key], keys))

    def spot(self, spot):
        if not spot["mode"] in Wsprnet.supportedModes:
            return
        with self.spotLock:
            if any(x for x in self.spots if self.spotEquals(spot, x)):
                # dupe
                pass
            else:
                self.spots.append(spot)
        self.scheduleNextUpload()

    def upload(self):
        try:
            with self.spotLock:
                spots = self.spots
                self.spots = []
            if spots:
                self.uploader.upload(spots)
                self.timer = None
        except Exception:
            logging.exception("Failed to upload spots")

    def cancelTimer(self):
        if self.timer:
            self.timer.cancel()
            self.timer.join()
        self.timer = None


class Uploader(object):

    def __init__(self, station: str, tmpdir):
        self.station = Config.get()["STATIONS"][station]
        self.station["name"] = station
        self.tmpdir = tmpdir
        self.logdir = Config.logdir()
        self._event = threading.Event()

    def upload(self, spots):
        logging.warning("uploading %i spots to wsprnet", len(spots))

        allmet = os.path.join(self.tmpdir, "allmet_%d.txt" % (
            int(time.time() + random.uniform(0, 99)) & 0xffff))
        spot_lines = []
        for spot in spots:
            # 200804 1916  0.26 -18  0.96   7.0401756 JA5NVN         PM74   37  0
            spot_lines.append("%s  %1.2f %d  %1.2f   %2.7f %s         %s   %d  %d\n" % (
                # wsprnet needs GMT time
                time.strftime("%y%m%d %H%M", time.gmtime(spot["timestamp"])),
                spot["sync_quality"],
                spot["db"],
                spot["dt"],
                # freq in MHz for wsprnet
                spot["freq"] / 1e6,
                spot["callsign"],
                spot["locator"],
                spot["watt"],
                spot["drift"]
            ))

        self.save(spot_lines, allmet)
        self.save(spot_lines, os.path.join(self.logdir, "wspr_all.log"))

        postfiles = {"allmept": open(allmet, "r")}
        params = {"call": self.station["callsign"],
                  "grid": self.station["grid"]}

        max_retries = 5
        retries = 0
        resp = None

        while True:
            try:
                requests.adapters.DEFAULT_RETRIES = 5
                s = requests.session()
                s.keep_alive = False
                resp = s.post("http://wsprnet.org/post", files=postfiles, params=params, timeout=300)

                if resp.status_code == 200:
                    #print(resp.text)
                    break
                
            # TODO: handle with retry
            except requests.ConnectionError or requests.exceptions.Timeout as e:
                logging.error("Wsprnet connection error %s", e)
                logging.warning("try again ...")
                self._event.wait(timeout=10)
                if retries >= max_retries:                    
                    logging.warning("Saving %d spot to wspr_upload_fail.log", len(spot_lines))
                    self.save(spot_lines, os.path.join(self.logdir, "wspr_upload_fail.log"))
                    break
                else:
                    retries += 1
                    continue
            except requests.exceptions.ReadTimeout as e:
                logging.error("Wsprnet read timeout error %s", e)
                break
        
        logging.debug("delete %s", allmet)
        os.unlink(allmet)

    def save(self, spot_lines, file):
        with open(file, "a") as file:
            file.writelines(spot_lines)