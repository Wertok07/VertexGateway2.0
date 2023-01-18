"""

"""
from Vertex.source.vertex.Vertex import Vertex
from Vertex.source.vertex.Device import Device
from Vertex.source.vertex.Group import Group
import bntest
import json


class MqttParseHelper:

    def __init__(self, gateway, bacnet, logger, config, client):
        self.gateway = gateway
        self.bacnet = bacnet
        self.logger = logger
        self.config = config
        self.client = client
        self.status_edges = False
        self.status_devices = False
        self.status_groups = False

    def edges(self, payload, uid_vertex, max_vertex):
        if len(uid_vertex) > max_vertex:
            self.logger.warn("Too many static Vertex UIDs defined, first 10 Vertex will be used")

        for vertex in payload:
            edge_type = payload[vertex]["edge_type"]
            if edge_type == "vertex3":
                if not (vertex in uid_vertex):
                    uid_vertex.append(vertex)

        for vertex in uid_vertex:
            ver = self.gateway.getVertex(vertex)
            if not (ver is None):
                ver.setStatus(True)
            else:
                ver = Vertex(vertex, bacnet_instance=self.gateway.getFreeVertexInstance(), _type="vertex3")
                ver.setStatus(True)
                if self.gateway.quantityVertex() <= max_vertex:
                    self.gateway.addVertex(ver)

        self.status_edges = True
        self.logger.message('Downloading information about Vertex completed')

    def devices(self, payload):

        for vertex in payload:
            edge_type = payload[vertex]["edge_type"]

            if edge_type == "vertex3":
                ver = self.gateway.getVertex(vertex)

                if not (ver is None):
                    for device in payload[vertex]["devices"]:
                        dev = self.gateway.getDevice(vertex, device)
                        if not (dev is None):
                            dev.setStatus(True)
                        else:
                            dev_type = payload[vertex]["devices"][device]['device_type']
                            if dev_type == 4:  # 4 LED luminaries
                                new_dev = Device(device,
                                                 bacnet_instance=self.gateway.getFreeDeviceInstance(vertex, dev_type),
                                                 dev_type=0)
                                ver.addDevice(new_dev)
                            elif dev_type == 128:  # 128 Dali 2 device
                                new_dev = Device(device,
                                                 bacnet_instance=self.gateway.getFreeDeviceInstance(vertex, dev_type),
                                                 dev_type=2)
                                ver.addDevice(new_dev)
                            elif dev_type == 3:  # 3 Emergency luminaries
                                new_dev = Device(device,
                                                 bacnet_instance=self.gateway.getFreeDeviceInstance(vertex, dev_type),
                                                 dev_type=4)
                                ver.addDevice(new_dev)
                            else:
                                self.logger.debug(f'The gateway does not support this type of device UID:{device}')
                """else:
                    ver = Vertex(vertex, edge_type)
                    ver.setStatus(True)
                    for device in payload[vertex]["devices"]:
                        dev_type = payload[vertex]["devices"][device]['device_type']
                        if dev_type == 4 or dev_type == 128:  # 4 LED luminaries | 128 Dali 2 device
                            ver.addDevice(Device(device))
                        else:
                            self.logger.debug(f'The gateway does not support this type of device UID:{device}')
                    self.gateway.addVertex(ver)"""

        self.status_devices = True
        self.logger.message('Downloading information about Devices completed')

    def groups(self, payload):
        for vertex in payload:
            edge_type = payload[vertex]["edge_type"]

            if edge_type == "vertex3":
                ver = self.gateway.getVertex(vertex)

                if not (ver is None):
                    for group in payload[vertex]["groups"]:
                        gro = self.gateway.getGroup(group)
                        if not (gro is None):
                            gro.setStatus(True)
                        else:
                            gro = Group(group, bacnet_instance=self.gateway.getFreeGroupInstance(vertex), dev_type=1)
                            gro.setStatus(True)
                            ver.addGroup(gro)

        self.status_groups = True
        self.logger.message('Downloading information about Groups completed')

    def all_light(self, payload, payload_for_bacnet):
        for light in payload:
            vertex_uid = payload[light]["vertex_uid"]
            vertex_bi = self.gateway.getVertex(vertex_uid).bacnet_instance
            light_bi = self.gateway.getDevice(payload[light]["vertex_uid"], payload[light]["uid"]).bacnet_instance
            light_type = self.gateway.getDevice(payload[light]["vertex_uid"], payload[light]["uid"]).dev_type

            obj1 = f'AV3{light_type}0{vertex_bi}{light_bi:03}.Present_Value'
            value1 = payload[light]['brightness']
            obj2 = f'AV3{light_type}0{vertex_bi}{light_bi:03}.Description'
            value2 = str(payload[light])

            if self.config.configuration_rename_with_port_and_short_address:
                obj3 = f'AV3{light_type}0{vertex_bi}{light_bi:03}.Name'
                value3 = f'VertexGateway_{vertex_uid}_{payload[light]["dali_port"]}_{payload[light]["short_address"]:02}'
                payload_for_bacnet[obj3] = value3

            payload_for_bacnet[obj1] = value1
            payload_for_bacnet[obj2] = value2

    def individual_button(self, vertex_id, dev_id, button, payload, payload_for_bacnet):

        vertex_bi = self.gateway.getVertex(vertex_id).bacnet_instance
        button_bi = self.gateway.getDevice(vertex_id, dev_id).bacnet_instance
        button_type = self.gateway.getDevice(vertex_id, dev_id).dev_type
        button_bi_edit = button_bi + int(button)

        if int(button) > 9:
            self.logger.warn("Too many button")
            return

        # BACnet point
        obj_bi = f'AV3{button_type}0{vertex_bi}{button_bi_edit:03}'

        if self.bacnet.find_object_by_id(obj_bi) is None and self.config.configuration_use_auto_create:
            # Create
            obj = obj_bi + '.Name'
            value = f'VertexGateway_{vertex_id}_{dev_id}_{button}'
            bacnet_queue = dict()
            bacnet_queue[obj] = value
            try:
                self.bacnet.write(bacnet_queue, request_type=bntest.OBJECT_CREATE)
                self.logger.message(f"Create button point [{obj_bi}] complete without error")
            except Exception as error:
                self.logger.debug(error)

        obj1 = obj_bi + '.Present_Value'
        val1 = int(payload["state"])

        obj2 = obj_bi + '.Units'
        val2 = ""

        obj3 = obj_bi + '.Decimal_Places'
        val3 = 0

        payload_for_bacnet[obj1] = val1
        payload_for_bacnet[obj2] = val2
        payload_for_bacnet[obj3] = val3

    def individual_sensor(self, vertex_id, dev_id, sensor_type, payload, payload_for_bacnet):

        vertex_bi = self.gateway.getVertex(vertex_id).bacnet_instance
        sensor_bi = self.gateway.getDevice(vertex_id, dev_id).bacnet_instance
        sensor_inst_type = self.gateway.getDevice(vertex_id, dev_id).dev_type
        name = 'motion'
        units = ""

        if sensor_type == "illuminance":
            sensor_bi += 1
            name = 'illuminance'
            units = 'lx'

        # BACnet point
        obj_bi = f'AV3{sensor_inst_type}0{vertex_bi}{sensor_bi:03}'

        if self.bacnet.find_object_by_id(obj_bi) is None and self.config.configuration_use_auto_create:
            # Create
            obj = obj_bi + '.Name'
            value = f'VertexGateway_{vertex_id}_{dev_id}_{name}'
            bacnet_queue = dict()
            bacnet_queue[obj] = value
            try:
                self.bacnet.write(bacnet_queue, request_type=bntest.OBJECT_CREATE)
                self.logger.message(f"Create button point [{obj_bi}] complete without error")
            except Exception as error:
                self.logger.debug(error)

        obj1 = obj_bi + '.Present_Value'
        val1 = int(payload[sensor_type])

        obj2 = obj_bi + '.Units'
        val2 = units

        obj3 = obj_bi + '.Decimal_Places'
        val3 = 0

        payload_for_bacnet[obj1] = val1
        payload_for_bacnet[obj2] = val2
        payload_for_bacnet[obj3] = val3

    def individual_light(self, vertex_id, dev_id, payload, payload_for_bacnet):

        try:
            vertex_bi = self.gateway.getVertex(vertex_id).bacnet_instance
            light_bi = self.gateway.getDevice(vertex_id, dev_id).bacnet_instance
            light_type = self.gateway.getDevice(vertex_id, dev_id).dev_type
        except Exception as error:
            self.logger.debug(f"There is no dev defined {error}")
            return

        obj1 = f'AV3{light_type}0{vertex_bi}{light_bi:03}.Present_Value'
        value1 = payload['brightness']
        obj2 = f'AV3{light_type}0{vertex_bi}{light_bi:03}.Description'
        value2 = str(payload)
        payload_for_bacnet[obj1] = value1
        payload_for_bacnet[obj2] = value2

    def groups_feedback(self, group_id, payload, payload_for_bacnet):
        try:
            group = self.gateway.getGroup(group_id)
            vertex = self.gateway.getVertexFromGroup(group_id)
            obj = f'AV310{vertex.bacnet_instance}{group.bacnet_instance:03}'
        except Exception as error:
            self.logger.debug(f"There is no group defined {error}")
            return

        if payload['value_type'] == 'direct':
            value = payload['value']
        elif payload['value_type'] == 'bool':
            if payload['value']:
                value = 101
            else:
                value = 0
        else:
            value = 0

        obj1 = obj + '.Present_Value'
        obj2 = obj + '.Description'
        value2 = str(payload)
        payload_for_bacnet[obj1] = int(value)
        payload_for_bacnet[obj2] = value2

    def write(self, payload_for_mqtt):
        self.logger.debug('Sending data to Vertex devices')
        for i in payload_for_mqtt:
            for j in i:
                if j['typ'] == 'group':
                    for topic in j['data']:
                        msg = json.dumps(j['data'][topic])
                        self.client.publish(topic, msg)

                if j['typ'] == 'devices':

                    value = {}
                    for elem in j['data']:
                        if elem[0] not in value:
                            value[elem[0]] = []
                        value[elem[0]].append(elem[1:])

                    for key in value:
                        topic = f'vertex3/light/{key}/brightness/set'
                        tmp_dict = {}
                        for i in value[key]:
                            tmp_dict[i[0]] = i[1]
                        msg = json.dumps(tmp_dict)
                        self.client.publish(topic, msg)
