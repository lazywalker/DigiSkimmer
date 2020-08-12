import logging
import threading

from .client import KiwiDownError, KiwiTooBusyError, KiwiTimeLimitError, KiwiServerTerminatedConnection

class KiwiWorker(threading.Thread):
    def __init__(self, target=None, name=None):
        super(KiwiWorker, self).__init__(target=target, name=name)
        self._recorder = target
        self._options = self._recorder._options
        self._recorder._reader = True
        self._event = threading.Event()
        self._run_event = threading.Event()

    def start(self):
        logging.info("Started sound recorder %s, timestamp=%d", self.getName(), self._options.timestamp)

        self._run_event.set()
        super(KiwiWorker, self).start()
        
    def run(self):
        self.connect_count = self._options.connect_retries

        while self._run_event.is_set():
            try:
                self._recorder.connect(self._options.server_host, self._options.server_port)
            except Exception as e:
                logging.error("Failed to connect, sleeping and reconnecting error='%s'", e)

                self.connect_count -= 1
                if self._options.connect_retries > 0 and self.connect_count == 0:
                    break
                if self._options.connect_timeout > 0:
                    self._event.wait(timeout = self._options.connect_timeout)
                continue

            try:
                self._recorder.open()
                while self._run_event.is_set():
                    self._recorder.run()
            except KiwiServerTerminatedConnection as e:
                if self._options.no_api:
                    msg = ''
                else:
                    msg = ' Reconnecting after 5 seconds'
                logging.warning("%s:%s %s.%s" % (self._options.server_host, self._options.server_port, e, msg))
                self._recorder.close()
                if self._options.no_api:    ## don't retry
                    break
                self._recorder._start_ts = None ## this makes the recorder open a new file on restart
                self._event.wait(timeout=5)
                continue
            except KiwiTooBusyError:
                logging.warning("%s:%d too busy now. Reconnecting after 15 seconds"
                      % (self._options.server_host, self._options.server_port))

                self._event.wait(timeout=15)
                continue
            except KiwiDownError:
                # kiwi is upgrading or something else
                logging.warning("%s:%d is down now. Reconnecting after 60 seconds"
                      % (self._options.server_host, self._options.server_port))

                self._event.wait(timeout=60)
                continue
            except KiwiTimeLimitError:
                logging.fatal("%s:%d is reaching time limited, i'm out."
                      % (self._options.server_host, self._options.server_port))
                break
            except Exception:
                logging.exception("KW Error")
                break

        self._run_event.clear()
        self._recorder.close()

    def stop(self):
        self._run_event.clear()
        logging.debug("KW thread %s stop.", self.getName())
