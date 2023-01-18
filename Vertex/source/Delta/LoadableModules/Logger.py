import datetime
from Delta import DeltaEmbedded
from Delta import LoadableModules
from pathlib import Path
import inspect

bacnet = DeltaEmbedded.BACnetInterface()

class Logger:

    MAX_LOG_ENTRIES = 20

    def __init__(self, fil_instance=None):
        """
        Instantiate new Logger with messages loaded from FIL object's description

        Arguments:
            fil_instance -- (optional) FIL object to map to. Not needed if used from a loadable
                module script, in this case it is found using loadable script name in the
                callstack.
        """
        if fil_instance is None:
            module_name, fil_instance = LoadableModules.find_module_in_callstack()

        self.fil_description_ref = f"fil{fil_instance}.description"
        self.messages = bacnet.read_value(self.fil_description_ref).splitlines()
    
    def _write_messages(self):
        bacnet.write({self.fil_description_ref: "\n".join(self.messages)})

    def clear(self):
        """Remove all entries."""
        self.messages = []
        self._write_messages()

    def log_status(self, message):
        """Add an entry."""
        trim_size = self.MAX_LOG_ENTRIES - 1
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.messages = self.messages[-trim_size: ] + [f"[{current_time}] {message}"]
        self._write_messages()

