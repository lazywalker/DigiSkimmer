from abc import ABC, abstractmethod


class LineParser(ABC):
    def __init__(self, callsign, grid):
        self.dial_freq = None
        self.station = None
        self.band = None
        self.callsign = callsign
        self.grid = grid

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

    def setStation(self, station: str):
        self.station = station
