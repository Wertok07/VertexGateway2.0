"""

"""


class Group:

    def __init__(self, _id, bacnet_instance, dev_type=None):
        self.id = _id
        self.bacnet_instance = bacnet_instance
        self.status = False
        self.bacnet_point_exist = False
        self.dev_type = dev_type

    def setStatus(self, boolean):
        self.status = boolean

    def getStatus(self):
        return self.status
