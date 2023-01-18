"""
Main storage of setting and data to vertex gateway
"""
from .LicenseManagerDecrypt import LicenseManagerDecrypt


class Gateway:

    def __init__(self, _license, vertex_ip, logger="", debug=0, max_vertex=10, max_points=1000, use_tags=False,
                 serial_number=""):
        self.license = _license
        self.debug = debug
        self.vertex_ip = vertex_ip
        self.max_vertex = max_vertex
        self.max_points = max_points
        self.use_tags = use_tags
        self.serial_number = serial_number
        self.vertex = []
        self.logger = logger

    def licenseIsValid(self):
        license_feedback = LicenseManagerDecrypt(self.license, self.logger)
        if license_feedback.decrypt() == self.serial_number:
            return True
        return False

    def licenseIsDev(self):
        license_feedback = LicenseManagerDecrypt(self.license, self.logger)
        return license_feedback.isDevModeAvaliable()

    def quantityVertex(self):
        return len(self.vertex)

    def quantityDevices(self):
        dev_number = 0
        for i in self.vertex:
            dev_number += len(i.devices)
        return dev_number

    def quantityGroups(self):
        group_number = 0
        for i in self.vertex:
            group_number += len(i.groups)
        return group_number

    def addVertex(self, vertex):
        self.vertex.append(vertex)

    def getVertex(self, _id):
        for i in self.vertex:
            if _id == i.id:
                return i
        return None

    def getFreeVertexInstance(self):
        # 0-9
        select = 0
        for i in self.vertex:
            if select == i.bacnet_instance:
                select += 1
                continue
        if select > 9:
            select = None
        return select

    def getFreeDeviceInstance(self, id_vertex, dev_type):
        vertex_pos = None
        if dev_type == 4:  # Light
            for i in self.vertex:
                if id_vertex == i.id:
                    vertex_pos = self.vertex.index(i)
                    break
            select = 0
            for i in self.vertex[vertex_pos].devices:
                if select == i.bacnet_instance and not (i.dev_type == 2 or i.dev_type == 3 or i.dev_type == 4):
                    select += 1
            if select > 999:
                select = None
        if dev_type == 3:  # Emergency light
            for i in self.vertex:
                if id_vertex == i.id:
                    vertex_pos = self.vertex.index(i)
                    break
            select = 0
            for i in self.vertex[vertex_pos].devices:
                if select == i.bacnet_instance and not (i.dev_type == 2 or i.dev_type == 3 or i.dev_type == 0):
                    select += 1
            if select > 999:
                select = None
        if dev_type == 128:  # Dali2 devices
            for i in self.vertex:
                if id_vertex == i.id:
                    vertex_pos = self.vertex.index(i)
                    break
            select = 0
            dev = None
            for i in self.vertex[vertex_pos].devices:
                if select == i.bacnet_instance and not (i.dev_type == 0 or i.dev_type == 4):
                    select += 10
                    dev = i
            if select > 999:
                if dev.dev_type >= 2 and dev.dev_type <= 3:
                    dev.dev_type += 1
                    select -= 1000
                else:
                    select = None
        return select

    def getFreeGroupInstance(self, id_vertex):
        vertex_pos = None
        for i in self.vertex:
            if id_vertex == i.id:
                vertex_pos = self.vertex.index(i)
                break
        select = 0
        for i in self.vertex[vertex_pos].groups:
            if select == i.bacnet_instance:
                select += 1
                continue
        if select > 999:
            select = None
        return select

    def getDevice(self, id_vertex, id_device):
        vertex_pos = None
        for i in self.vertex:
            if id_vertex == i.id:
                vertex_pos = self.vertex.index(i)
                break
        for i in self.vertex[vertex_pos].devices:
            if id_device == i.id:
                return i
        return None

    def getGroup(self, id_group):
        for i in self.vertex:
            for j in i.groups:
                if id_group == j.id:
                    return j
        return None

    def getVertexFromGroup(self, id_group):
        for i in self.vertex:
            for j in i.groups:
                if id_group == j.id:
                    return i
        return None

    def bacnetPointsExistChecker(self, bacnet):
        for i in self.vertex:
            for j in i.devices:
                instance = f"AV300{i.bacnet_instance}{j.bacnet_instance:03}"
                if not (bacnet.find_object_by_id(instance) is None):
                    j.bacnet_point_exist = True

    def getIdFromInstanceDev(self, vertex_instance, point_instance):
        _id = []
        for i in self.vertex:
            if i.bacnet_instance == int(vertex_instance):
                for j in i.devices:
                    if j.bacnet_instance == int(point_instance):
                        _id.append(i.id)
                        _id.append(j.id)
                        return _id
        return None

    def getIdFromInstanceGroup(self, vertex_instance, point_instance):
        _id = []
        for i in self.vertex:
            if i.bacnet_instance == int(vertex_instance):
                for j in i.groups:
                    if j.bacnet_instance == int(point_instance):
                        _id.append(i.id)
                        _id.append(j.id)
                        return _id
        return None

    def getIdFromInstance(self, instance):
        _id = []
        if int(instance[3]) == 1:
            for i in self.vertex:
                if i.bacnet_instance == int(instance[5]):
                    for j in i.groups:
                        if j.bacnet_instance == int(instance[6:]):
                            _id.append(i.id)
                            _id.append(j.id)
                            return _id
        else:
            for i in self.vertex:
                if i.bacnet_instance == int(instance[5]):
                    for j in i.devices:
                        if j.bacnet_instance == int(instance[6:]):
                            _id.append(i.id)
                            _id.append(j.id)
                            return _id
        return None

    def clearStatus(self):
        for i in self.vertex:
            i.setStatus(False)
            for j in i.devices:
                j.setStatus(False)
            for j in i.groups:
                j.setStatus(False)

    def reconfigureStatus(self):
        vertex_to_delete = []
        for i in self.vertex:
            if not i.getStatus():
                vertex_to_delete.append(i)

        vertex = [x for x in self.vertex if x not in vertex_to_delete]
        self.vertex = vertex

        devices_to_delete = []
        groups_to_delete = []
        for i in self.vertex:
            for j in i.devices:
                if not j.getStatus():
                    devices_to_delete.append(j)
            if (not (len(i.devices) == len(devices_to_delete))) and (i.getStatus()):
                devices = [x for x in i.devices if x not in devices_to_delete]
                i.devices = devices
            devices_to_delete = []

            for j in i.groups:
                if not j.getStatus():
                    groups_to_delete.append(j)
            if (not (len(i.groups) == len(groups_to_delete))) and (i.getStatus()):
                groups = [x for x in i.groups if x not in groups_to_delete]
                i.groups = groups
            groups_to_delete = []


if __name__ == "__main__":

    from Vertex import Vertex
    from Device import Device
    from Group import Group

    gateway = Gateway(
        "gAAAAABjNZgJ1JCi0p0bNi9TPEyTwJd3GIYQxX9EB7Pa8yMTpBL746Ai7-w7S03nC5FWTfJwU0FA3LYvVgcQ8qTRyOMadszd-w==",
        ["10.1.10.95"],
        max_vertex=10,
        max_points=1000,
        use_tags=False,
    )

    print("Licencja jest ważna?", gateway.licenseIsValid())

    for i in range(1, 6):
        ver = Vertex(f"B827EB0C25C{i}", i, "vertex3")
        for j in range(51, 61):
            ver.addDevice(Device(f"GF27EB0C25{j}", (i * 100) + j))
        for j in range(51, 61):
            ver.addGroup(Group(f"GF29EB0D25{j}", (i * 100) + j))
        gateway.addVertex(ver)

    gateway.clearStatus()
    pp_v = gateway.quantityVertex()
    pp_d = gateway.quantityDevices()
    pp_g = gateway.quantityGroups()
    print("pp", pp_v, pp_d, pp_g)

    for i in range(2, 5):
        ver = gateway.getVertex(f"B827EB0C25C{i}")
        if not ver is None:
            ver.setStatus(True)
            for j in range(52, 55):
                dev = gateway.getDevice(f"B827EB0C25C{i}", f"GF27EB0C25{j}")
                if not dev is None:
                    if not (i == 4):
                        dev.setStatus(True)
                else:
                    ver.addDevice(Device(f"GF27EB0C25{j}", (i * 100) + j))
        else:
            ver = Vertex(f"B827EB0C25C{i}", i, "vertex3")
            ver.setStatus(True)
            for j in range(52, 55):
                ver.addDevice(Device(f"GF27EB0C25{j}", (i * 100) + j))

    gateway.reconfigureStatus()

    po_v = gateway.quantityVertex()
    po_d = gateway.quantityDevices()
    po_g = gateway.quantityGroups()
    print("po", po_v, po_d, po_g)

    if ((int(pp_v) - int(po_v)) == 2):
        print('\x1b[6;30;42m' + "Usuwanie vertexów - OK!" + '\x1b[0m')
    else:
        print('\x1b[2;30;41m' + "Usuwanie vertexów - Error" + '\x1b[0m')

    if ((int(pp_d) - int(po_d)) == 34):
        print('\x1b[6;30;42m' + "Usuwanie devices - OK!" + '\x1b[0m')
    else:
        print('\x1b[2;30;41m' + "Usuwanie devices - Error" + '\x1b[0m')

    if ((int(pp_g) - int(po_g)) == 20):
        print('\x1b[6;30;42m' + "Usuwanie groups - OK!" + '\x1b[0m')
    else:

        print('\x1b[2;30;41m' + "Usuwanie groups - Error" + '\x1b[0m', pp_g, po_g)

    """
    print(gateway.getVertex("B827EB0C25C1"))
    print(gateway.getVertex("B827EB0C25C3").id)
    print(gateway.getVertex("B827EB0C25C5").id)
    print(gateway.getVertex("B827EB0C25C1").bacnet_instance)
    print(gateway.getVertex("B827EB0C25C3").bacnet_instance)
    print(gateway.getVertex("B827EB0C25C5").bacnet_instance)
    print(gateway.quantityVertex())

    print(gateway.getDevice("B827EB0C25C1", "GF27EB0C2555").bacnet_instance)
    print(gateway.getIdFromInstance(1, 155))
    print(gateway.getIdFromInstance(3, 358))
    print(gateway.getIdFromInstance(5, 558))
    print(gateway.quantityDevices())
    """
