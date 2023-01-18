"""
Vertex storage of setting and data
"""


class Vertex:

    def __init__(self, _id, bacnet_instance, _type=""):
        self.id = _id
        self.bacnet_instance = bacnet_instance
        self.groups = []
        self.devices = []
        self.type = _type
        self.status = False

    def addDevice(self, device):
        self.devices.append(device)

    def addGroup(self, group):
        self.groups.append(group)

    def setStatus(self, boolean):
        self.status = boolean

    def getStatus(self):
        return self.status
