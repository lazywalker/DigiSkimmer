from abc import ABC, abstractmethod


class LineParser(ABC):
    def __init__(self, station: str):
        self.dial_freq = None
        self.band = None
        self.station = station

    @abstractmethod
    def parse(self, raw):
        pass

    def setDialFrequency(self, freq):
        self.dial_freq = freq

    def getBand(self):
        return self.band

    def setBand(self, band: str):
        self.band = band

    def getStation(self):
        return self.station
