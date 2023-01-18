from Delta import LoadableModules

LEVEL_NONE = 0
LEVEL_WARN = 1
LEVEL_ERROR = 2
LEVEL_MESSAGE = 3
LEVEL_DEBUG = 4


class Logger:
    """
    Wrapper for the LoadableModules Logger
    """

    def __init__(self, fil_instance=None, level=LEVEL_ERROR):
        """
        Configure the logger
        """
        self.__level = level
        self.__fil_instance = fil_instance
        self.__logger = LoadableModules.Logger(fil_instance=fil_instance)

    def set_level(self, level=LEVEL_ERROR):
        """
        Specify the current logging level
        """
        self.__level = level

    def write(self, message, level=LEVEL_MESSAGE):
        """
        Add an item to the log if applicable
        """
        if level <= self.__level:
            # Print the message to the console
            if self.__fil_instance is not None:
                print(message)

            # Add the message to the FIL log
            self.__logger.log_status(message)

    def debug(self, message):
        """
        Write a debug message

        :param message:
        :return:
        """
        if (self.__fil_instance is None):
            self.write(f"DBG: {message}", level=LEVEL_DEBUG)
        else:
            self.write(f"\033[33mDBG: {message}\033[0m", level=LEVEL_DEBUG)

    def message(self, message):
        """
        Write a regular message

        :param message:
        :return:
        """
        self.write(f"MSG: {message}", level=LEVEL_MESSAGE)

    def warn(self, message):
        """
        Write a Warning message

        :param message:
        :return:
        """
        self.write(f"WRN: {message}", level=LEVEL_WARN)

    def error(self, message):
        """
        Write an error message

        :param message:
        :return:
        """
        if (self.__fil_instance is None):
            self.write(f"ERR: {message}", level=LEVEL_ERROR)
        else:
            self.write(f"\033[31mERR: {message}\033[0m", level=LEVEL_ERROR)

    def clear(self):
        """
        Clear the log / remove all entries
        """
        self.__logger.clear()
