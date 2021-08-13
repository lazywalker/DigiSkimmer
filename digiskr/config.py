import importlib.util
import logging
import json

VERSION = '0.34.1'
KIWI_USER = "digiskr_%s" % VERSION
DECODING_SOFTWARE = "DigiSkimmer %s" % VERSION
MODES = {'~': 'FT8', '#': 'JT65', '@': 'JT9', '+': 'FT4', '!': 'WSPR', '`': 'FST4W'}
BANDS = {  # Freq in MHz
    'FT8': {'160': 1.840, '80': 3.573, '60': 5.357, '40': 7.074, '30': 10.136, '20': 14.074, '17': 18.100, '15': 21.074, '12': 24.915, '10': 28.074, '6': 50.313, '2': 144.174},
    'FT4': {'80': 3.575, '40': 7.0475, '30': 10.140, '20': 14.080, '17': 18.104, '15': 21.140, '12': 24.919, '10': 28.180, '6': 50.318, '2': 144.170},
    'JT65': {'160': 1.838, '80': 3.570, '40': 7.076, '30': 10.138, '20': 14.076, '17': 18.102, '15': 21.076, '12': 24.917, '10': 28.076, '6': 50.310, '2': 144.120},
    'JT9': {'160': 1.839, '80': 3.572, '40': 7.078, '30': 10.140, '20': 14.078, '17': 18.104, '15': 21.078, '12': 24.919, '10': 28.078, '6': 50.312},
    'WSPR': {
        '2190': 0.136000, '630': 0.474200, '160': 1.836600, '80': 3.568600, '60': 5.364700, '40': 7.038600, '30': 10.138700,
        '20': 14.095600, '17': 18.104600, '15': 21.094600, '12': 24.924600, '10': 28.124600, '6': 50.293000,
        '2': 144.489000, '0.7': 432.300000,
        # 5.287200 is a 60m frequency used in some countries like UK.
        # 3.592600 is the old 80m frequency, which should technically not be used anymore, 
        # but is still used by some people (suggested by Stefan HB9TMC).
        '81': 3.592600, '61': 5.287200,
    },
    'FST4': {'2190': 0.136000, '630': 0.474200, '160': 1.839000},
    'FST4W': {'2190': 0.136000, '630': 0.474200, '160': 1.836800},
}


class ConfigNotFoundException(Exception):
    pass


class ConfigError(object):
    def __init__(self, key, message):
        self.key = key
        self.message = message

    def __str__(self):
        return "Configuration Error (key: {0}): {1}".format(self.key, self.message)


class Config:
    instance = None

    @staticmethod
    def _loadPythonFile(file):
        spec = importlib.util.spec_from_file_location("settings", file)
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        conf = {}
        for name, value in cfg.__dict__.items():
            if name.startswith("__"):
                continue
            conf[name] = value
        return conf

    @staticmethod
    def _loadJsonFile(file):
        with open(file, "r") as f:
            conf = {}
            for k, v in json.load(f).items():
                conf[k] = v
            return conf

    @staticmethod
    def _loadConfig():
        for file in ["/opt/digiskr/settings.py", "./settings.py", "./settings.json"]:
            try:
                if file.endswith(".py"):
                    return Config._loadPythonFile(file)
                elif file.endswith(".json"):
                    return Config._loadJsonFile(file)
                else:
                    logging.warning("unsupported file type: %s", file)
            except FileNotFoundError:
                pass
        raise ConfigNotFoundException(
            "no usable config found! please make sure you have a valid configuration file!")

    @staticmethod
    def get():
        if Config.instance is None:
            Config.instance = Config._loadConfig()
        return Config.instance

    @staticmethod
    def store():
        with open("settings.json", "w") as file:
            json.dump(Config.get().__dict__(), file, indent=4)

    @staticmethod
    def validateConfig():
        conf = Config.get()
        errors = [
            Config.checkTempDirectory(conf)
        ]

        errors += [
            Config.checkStations(conf)
        ]

        return [e for e in errors if e is not None]

    @staticmethod
    def checkTempDirectory(conf: dict):
        if "TMP_PATH" not in conf or conf["TMP_PATH"] is None:
            return ConfigError("TMP_PATH", "temporary directory is not set")

        return None

    @staticmethod
    def checkStations(conf: dict):
        key = "STATIONS"
        if key not in conf or conf[key] is None:
            return ConfigError(key, "STATIONS is not set")

        for k, v in conf[key].items():
            if not "callsign" in v:
                return ConfigError(key, "%s->callsign is not set" % k)

        return None

    @staticmethod
    def tmpdir():
        conf = Config.get()
        return conf["TMP_PATH"] if "TMP_PATH" in conf else "./tmp/digiskr/"

    @staticmethod
    def logdir():
        conf = Config.get()
        return conf["LOG_PATH"] if "LOG_PATH" in conf else "./log/"
