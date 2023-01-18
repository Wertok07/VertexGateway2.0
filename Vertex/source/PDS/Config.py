import json
import PDS
from .Log import *


class _CSVConfigObject:
    """
    A Configuration Object, referencing a BACnet CSV object.
    """

    def __init__(self, object_name, bacnet_interface, logger, defaults_path=None, change_callback=None, device=None):
        """
        Create the configuration object.

        :param object_name: The CSV object name.
        :param bacnet_interface: A BACnet interface for reading/writing to BACnet.
        :param logger: The PDS.Log.Logger object that this configuration object can write to.
        :param defaults_path: Location of a JSON file that contains the default value for this object
        :param change_callback: Can be provided a callable function to execute when this configuration item has changed.
        :param device: Device parameter (if not local).

        :return: None
        """

        # Type checking
        if not isinstance(bacnet_interface, PDS.BACnet.Interface):
            raise TypeError("Provided BACnet Interface is not valid")
        if not isinstance(logger, PDS.Log.Logger):
            raise TypeError("Provided Logger interface is not valid")

        # Interfaces, callbacks, etc
        self.__bacnet_interface = bacnet_interface
        self.__logger = logger
        self.__change_callback = change_callback
        self.__device = device
        self.__defaults_path = defaults_path

        # Object Details
        self.__object_name = object_name
        self.__logger.debug(f"Initializing Configuration Object {self.__object_name}")

        if self.__device is None:
            self.__obj_ref = self.__bacnet_interface.find_object_by_name(
                obj_name=self.__object_name,
                obj_type="CSV"
            )
        else:
            self.__obj_ref = self.__bacnet_interface.find_object_by_name(
                obj_name=self.__object_name,
                obj_type="CSV",
                device=self.__device
            )

        if self.__obj_ref is None:
            raise Exception("Configuration object {obj} could not be found".format(
                obj=self.__object_name))

        self.__obj_value = self.__bacnet_interface.read_value(self.__obj_ref + ".present_value")
        if len(self.__obj_value) == 0:
            raise Exception("Configuration object {obj} was empty".format(
                obj=self.__object_name))

        self.__data = json.loads(self.__obj_value)

    def check_for_update(self, skip_callbacks=False):
        """
        Read the object from BACnet to determine if it has changed.

        :return: None
        """
        if self.__device is None:
            obj_ref = self.__bacnet_interface.find_object_by_name(
                obj_name=self.__object_name,
                obj_type="CSV"
            )
        else:
            obj_ref = self.__bacnet_interface.find_object_by_name(
                obj_name=self.__object_name,
                obj_type="CSV",
                device=self.__device
            )

        if obj_ref is None:
            raise Exception("Configuration object {obj} could not be found".format(obj=self.__object_name))

        # Check if the configuration object reference has changed
        if obj_ref != self.__obj_ref:
            self.__logger.message("Config object changed: {} <> {}".format(obj_ref, self.__obj_ref))
            self.__obj_ref = obj_ref

        # Check if the configuration value has changed
        obj_value = self.__bacnet_interface.read_value(self.__obj_ref + ".present_value")
        if obj_value != self.__obj_value:
            self.__obj_value = obj_value
            self.__data = json.loads(obj_value)
            self.__logger.message("Config string {} changed".format(self.__object_name))

            if not skip_callbacks and self.__change_callback and callable(self.__change_callback):
                self.__change_callback()

    def set(self, data):
        """
        Write the object to internal tracking and to BACnet.

        :param data: JSON Data to write (passed as dict).
        """
        if not (isinstance(data, dict) or isinstance(data, list) or isinstance(data, str)):
            raise TypeError("Provided data is not a valid type")

        obj_value = json.dumps(data)
        if obj_value == self.__obj_value:
            # Skip write if the sent object value is the same as the stored object value
            return

        # Set internal variables
        self.__obj_value = obj_value
        self.__data = data

        # Write to BACnet
        self.__bacnet_interface.write({self.__obj_ref + ".present_value": obj_value})

    def get(self):
        """
        Gets the formatted data for this configuration object
        """
        return self.__data


class CSVConfigManager:
    """
    Manages CSV Configuration objects and converts to JSON
    """

    def __init__(self, bacnet_interface, logger, device=None):
        """
        Initialize the configuration items dictionary.

        :param bacnet_interface: A BACnet interface for reading/writing to BACnet.
        :param logger: A reference to the logger that the configuration object can use.
        :param device: Device parameter (if not local).

        :return: None
        """

        # Type checking
        if not isinstance(bacnet_interface, PDS.BACnet.Interface):
            raise TypeError("Provided BACnet Interface is not valid")
        if not isinstance(logger, PDS.Log.Logger):
            raise TypeError("Provided Logger interface is not valid")

        self.__items = dict()

        self.__bacnet_interface = bacnet_interface
        self.__device = device

        self.__logger = logger

    def add(self, object_name, change_callback=None):
        """
        Add a configuration item to the list (by object name)

        :param object_name: The CSV object name.
        :param change_callback: Can be provided a callable function to execute when this configuration item has
            changed.  The intent is to catch writes from outside of the integration, as the config manager assumes
            that internal writes will properly call CSVConfigManager.set for a configuration item.

        :return: None
        """
        if object_name in self.__items:
            raise Exception("{name} is already specified as a configuration item".format(name=object_name))

        # Add it to our configuration
        self.__items[object_name] = _CSVConfigObject(
            object_name=object_name,
            logger=self.__logger,
            bacnet_interface=self.__bacnet_interface,
            change_callback=change_callback,
            device=self.__device
        )

    def get(self, object_name):
        """
        Return mapping data dictionary for a specified object_name.

        :param object_name: The CSV object name.

        :return: dict
        """
        if object_name not in self.__items:
            raise KeyError("Configuration object {obj} does not exist".format(obj=object_name))

        return self.__items[object_name].get()

    def set(self, object_name, data):
        """
        Set a configuration item with JSON data for a specified object_name.

        :param object_name: The CSV object name.
        :param data: JSON-dumpable data to write.

        :return: None
        """
        if object_name not in self.__items:
            raise KeyError("Configuration object {obj} does not exist".format(obj=object_name))

        self.__items[object_name].set(data)

    def check_all_for_update(self):
        """
        Check for an update of all known configuration items.
        """
        self.__logger.debug("Updating all configuration objects...")

        for object_name, config_object in self.__items.items():
            # Skip items that are not configuration items
            if not isinstance(config_object, _CSVConfigObject):
                continue

            try:
                config_object.check_for_update()
            except Exception as error:
                self.__logger.error(
                    "Configuration update error for {obj}: {e}".format(obj=object_name, e=error))
