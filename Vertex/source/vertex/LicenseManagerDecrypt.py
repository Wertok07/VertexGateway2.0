"""
License: Apache Software License, BSD License (BSD-3-Clause OR Apache-2.0)
"""
# Package loading
import sys
from .StaticData import LICENSE_DECRYPT_KEY
from os.path import dirname, abspath, join
pathfile = dirname(dirname(dirname(abspath(__file__))))
sys.path.append(join(pathfile, 'packages'))

from cryptography.fernet import Fernet

class LicenseManagerDecrypt:

    def __init__(self, licens, logger=None):
        self.__vertex_key = LICENSE_DECRYPT_KEY
        self.licens = licens.encode('utf-8')
        self.logger = logger
        self.dev_mode = False

    def decrypt(self):
        tmp = ""
        try:
            tmp = self.__decrypt_raw(self.licens, self.__vertex_key).decode()
            if len(tmp) == 0:
                self.logger.warn("There is no license key")
                return None
            tmp = tmp.split("_")
            if len(tmp) > 1:
                if tmp[1] == "DEV":
                    self.dev_mode = True
        except Exception as error:
            self.logger.debug("License key error")
            if not len(tmp):
                if not (self.logger == None):
                    self.logger.warn("There is no license key")
            else:
                if not (self.logger == None):
                    self.logger.error(f"LicenseManagerDecrypt error: {error}")
            return None
        return tmp[0]

    def isDevModeAvaliable(self):
        return self.dev_mode


    def __decrypt_raw(self, token: bytes, key: bytes) -> bytes:
        return Fernet(key).decrypt(token)


if __name__ == "__main__":
    license = LicenseManagerDecrypt("gAAAAABjLWjEBhbykIbhrl2TnNwFBx2rRKJOu-09hVOTe1QUTAFnk3Ks404sb3CxWDNVgNrljTDz37GdAA8XQ7xFS9z-_4iYIQ==")
    print(f"Poprawność licencji 1: {license.decrypt()}")
    license2 = LicenseManagerDecrypt("")
    print(f"Poprawność licencji 2: {license2.decrypt()}")
