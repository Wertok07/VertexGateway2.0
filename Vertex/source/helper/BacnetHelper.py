"""

"""
import bntest


class BacnetHelper:

    def __init__(self, gateway, bacnet, logger, config):
        self.gateway = gateway
        self.bacnet = bacnet
        self.logger = logger
        self.config = config
        self.group_set = dict()
        self.device_set = []

    def create_bacnet_points(self):
        if not self.config.configuration_use_auto_create:
            self.logger.message("Automatic point creation disabled")
            return
        self.logger.message("Automatic point creation enabled")

        bacnet_queue = dict()

        for vertex in self.gateway.vertex:
            for dev in vertex.devices:
                obj = f'AV3{dev.dev_type}0{vertex.bacnet_instance}{dev.bacnet_instance:03}.Name'
                value = f'VertexGateway_{vertex.id}_{dev.id}'
                bacnet_queue[obj] = value
            for group in vertex.groups:
                obj = f'AV3{group.dev_type}0{vertex.bacnet_instance}{group.bacnet_instance:03}.Name'
                value = f'VertexGateway_{vertex.id}_{group.id}'
                bacnet_queue[obj] = value

        try:
            self.bacnet.write(bacnet_queue, request_type=bntest.OBJECT_CREATE)
            self.logger.message("Automatic point creation complete without error")
        except Exception as error:
            self.logger.debug(error)

    def write(self, payload_for_bacnet):
        if len(payload_for_bacnet) == 0:
            return
        try:
            self.bacnet.write(payload_for_bacnet)
            self.logger.debug("Save to BACnet point complete without error")
        except Exception as error:
            self.logger.debug(error)

    def read(self, payload_from_bacnet):

        value_return = []
        value_bacnet_return = {}

        if len(payload_from_bacnet) == 0:
            return

        try:
            response = self.bacnet.read(payload_from_bacnet)

            for i in response:
                dev, ref, prop = i.split('.')

                if not (int(ref[4]) == 1):
                    break

                if int(ref[3]) == 1:
                    # Group
                    if prop == "present_value":
                        if not (int(response[i]) == 255):
                            #MQTT
                            priority = dev + "." + ref + ".description"
                            if response[priority] == "":
                                value = {
                                    "value": int(response[i])
                                }
                            else:
                                value = {
                                    "value": int(response[i]),
                                    "priority": int(response[priority])
                                }

                            if (ref[:2]) == "av":
                                topic = f'vertex3/group/{self.gateway.getIdFromInstance(ref)[1]}/brightness/set'
                                self.group_set[topic] = value

                                # BACnet
                                obj1 = f'{ref.upper()}.Reset'
                                value1 = '1'
                                value_bacnet_return[obj1] = value1
                            else:
                                if not (int(response[i]) == 17):
                                    topic = f'vertex3/group/{self.gateway.getIdFromInstance(ref)[1]}/scene/set'
                                    self.group_set[topic] = value
                                    print(topic, value)
                                    # BACnet
                                    obj1 = f'{ref.upper()}.Reset'
                                    value1 = '1'
                                    value_bacnet_return[obj1] = value1

                elif int(ref[3]) == 0:

                    # Device
                    if (ref[:2]) == "av":
                        if prop == "present_value":
                            if not (int(response[i]) == 255):
                                tmp_list = []
                                uid = self.gateway.getIdFromInstance(ref)[0]
                                _id = self.gateway.getIdFromInstance(ref)[1]
                                val = int(response[i])

                                tmp_list.append(uid)
                                tmp_list.append(_id)
                                tmp_list.append(val)

                                self.device_set.append(tmp_list)

                                obj1 = f'{ref.upper()}.Reset'
                                value1 = '1'
                                value_bacnet_return[obj1] = value1

            if len(self.group_set):
                value1 = {
                    'typ': 'group',
                    'data': self.group_set
                }
                value_return.append(value1)
            if len(self.device_set):
                value2 = {
                    'typ': 'devices',
                    'data': self.device_set
                }
                value_return.append(value2)

            self.logger.debug("Read from BACnet point complete without error")
        except Exception as error:
            self.logger.debug(error)

        return_list = []
        return_list.append(value_return)
        return_list.append(value_bacnet_return)
        return return_list
