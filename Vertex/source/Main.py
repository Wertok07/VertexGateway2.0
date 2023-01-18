"""
Gateway to integrate Vertex device with O3-DIN
"""
# Package loading
import sys
from os.path import dirname, abspath, join

pathfile = dirname(dirname(abspath(__file__)))
sys.path.append(join(pathfile, 'packages'))

# Other lib
import paho.mqtt.client as mqtt

# Custom my lib
from vertex.StaticData import VERTEX_USERNAME, VERTEX_PASSWORD
from helper.ConfigFileHelper import ConfigFileHelper
from helper.MqttParseHelper import MqttParseHelper
from helper.BacnetHelper import BacnetHelper
from vertex.Gateway import Gateway

# DCI approve
from pathlib import Path
import bntest
import pickle
import json
import time
import os
import argparse
import schedule
from PDS.Log import Logger
from PDS.BACnet import Interface

INTERFACE_NAME = 'VertexGateway 2.0'
SETTINGS_FILE_NAME = 'Vertex_Settings_Config_CSV'
VERTEX_MQTT_USERNAME = VERTEX_USERNAME
VERTEX_MQTT_PASSWORD = VERTEX_PASSWORD


class Main:

    def __init__(self, device=None, username=None, password=None, site=None, debug=None):
        """
        Initialize the interface
        """
        try:
            self.device = device
            self.username = username
            self.password = password
            self.site = site
            self.debug = debug
            self.init_completed = False
            self.vertex_ip_choose_during_reconnect = 0
            self.topic_to_send = 0
            self.topic_to_send_for_light = 0
            self.reconnect = None
            self.counter_for_run = 0
            self.counter_for_bacnet = 500
            self.counter_for_mqtt = 500
            self.payload_for_bacnet = {}
            self.payload_from_bacnet = []
            self.payload_for_mqtt = []

            """
            MQTT Topics
            """
            self.mqtt_topics = [("discovery/edges", 0), ("discovery/devices", 0), ("discovery/groups", 0),
                                ("vertex3/light/+/state", 0),
                                ("vertex3/light/+/+/state", 0),
                                ("vertex3/group/+/feedback/state", 0),
                                ("vertex3/sensor/+/+/+/state", 0),
                                ("vertex3/button/+/+/+/state", 0)]

            """
            Set up the logger (for writing to the FIL object)
            """
            # If a device is provided, we will default to using FIL100 (on the local enteliWEB
            # BACnet device) as our logging output.  If we are running as a local interface (on an O3,
            # passing None will make it default to the FIL object containing the DLM)
            file = None
            if self.device:
                file = 100

            self.logger = Logger(fil_instance=file)
            self.logger.set_level(4)
            self.logger.clear()
            self.logger.message(f"Initializing '{INTERFACE_NAME}' interface...")
            self.logger.message(f"✅ Logger initialized")

            """
            Set up the interface
            """
            self.bacnet = Interface(user=self.username, password=self.password, site=self.site, device=self.device)
            # If a device is provided via the command prompt (ex: running through PyCharm),
            # reconfirm the device to allow the local machine's quattro to fully load it and avoid
            # any read errors
            if self.device:
                self.logger.debug("Reconfirming device...")
                self.bacnet.reconfirm_device(self.device)
            self.bacnet.register_alarm_callback(self.alarm_callback)
            self.logger.message(f"✅ Interface initialized")
            # **********************************************************************************************************
            """
            Set up the config manager
            """
            self.config_file_helper = ConfigFileHelper(SETTINGS_FILE_NAME, self.bacnet, self.logger, self.device)

            if self.config_file_helper.addConfig():
                self.logger.message("✅ Settings file initialized")
            else:
                self.logger.warn("Bad configuration of the settings file")
                return

            if self.config_file_helper.getConfig():
                self.logger.message("✅ Configuration read properly")

            schedule.every(self.config_file_helper.configuration_setting_file_refresh).seconds.do(
                self.config_file_helper.check_all_for_update).tag('settings', 'configuration')

            """
            Set up Vertex broker
            """
            model_name = self.bacnet.read_value(f'DEV{self.device}.Model_Name')
            serial_number = self.bacnet.read_value(f'DEV{self.device}.Serial_Number')
            self.client_name = f"{model_name}_{serial_number}"
            self.client = mqtt.Client(self.client_name)  # create new instance
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message
            self.logger.message(f"✅ Vertex communication interface initialized")

            """
            Set up Gateway
            """
            # Load data (deserialize)
            if Path(join(pathfile, 'config/gateway.pickle')).is_file():
                with open(join(pathfile, 'config/gateway.pickle'), 'rb') as handle:
                    self.gateway = pickle.load(handle)

                self.logger.message(f"Load configuration from database")
            else:
                self.gateway = Gateway(self.config_file_helper.configuration_license,
                                       self.config_file_helper.vertex_ip_vertex,
                                       self.logger,
                                       max_vertex=self.config_file_helper.vertex_max_vertex,
                                       max_points=self.config_file_helper.vertex_max_bacnet_points,
                                       use_tags=self.config_file_helper.configuration_use_tags,
                                       serial_number=serial_number,
                                       )
                self.logger.message(f"Generate configuration")
            """
            Set up BACnet Helper
            """
            self.bacnet_helper = BacnetHelper(self.gateway, self.bacnet, self.logger, self.config_file_helper)
            """
            Set up MQTT Helper
            """
            self.mqtt_helper = MqttParseHelper(self.gateway, self.bacnet, self.logger, self.config_file_helper,
                                               self.client)

            self.init_completed = True
        except Exception as error:
            self.logger.error(f"Main| {error}")
            return

    def init_completed(self):
        return self.init_completed

    def alarm_callback(self, alarm_notification):
        """
        alarm callback
        """
        try:
            _type = alarm_notification.gettype()
            if _type == bntest.ALARM_ADD:
                alarm_object = alarm_notification.getalarminfo()
                cref_input = alarm_object.getinputref()
                ref = str(cref_input).split('.')[-2]
                ref_back = ref[:4] + "0" + ref[5:]

                if self.gateway.getIdFromInstance(ref_back) is None:
                    return
                self.payload_from_bacnet.append(f"{ref}.Present_Value")
                self.payload_from_bacnet.append(f"{ref}.Description")
                self.counter_for_bacnet = 0

        except Exception as error:
            self.logger.error(f"Error processing alarm: {error}")

    def dump_gateway(self):
        with open(join(pathfile, 'config/gateway.pickle'), 'wb') as handle:
            pickle.dump(self.gateway, handle, protocol=pickle.HIGHEST_PROTOCOL)

        self.logger.message(f"Saving configuration to database")

    def run(self):
        pass
        """
        Connects a device, sends data, and receives data.
        """
        self.logger.message(f"Running '{INTERFACE_NAME}' interface...")

        # schedule.every(1).seconds.do(self.receive_alarm_and_sending_to_vertex)

        self.connect_to_vertex()
        """
        Loop Forever
        """
        while True:

            try:
                # Run any pending tasks, if there are any.  Try/Catch so that we do not break
                # the scheduler if there are any exceptions in any running task
                if self.counter_for_run > 8:
                    schedule.run_pending()
                    self.counter_for_run = 0

            except Exception as error:
                self.logger.error(f"ERR: Error running scheduled events - {error}")

            if self.counter_for_bacnet > 9999:
                self.counter_for_bacnet = 1000
            if self.counter_for_mqtt > 9999:
                self.counter_for_mqtt = 1000

            if self.counter_for_bacnet == self.config_file_helper.configuration_sending_time_ms:

                if len(self.payload_for_bacnet):
                    self.bacnet_helper.write(self.payload_for_bacnet)
                    self.payload_for_bacnet = {}

                if len(self.payload_from_bacnet):
                    list = self.bacnet_helper.read(self.payload_from_bacnet)

                    if len(list[0]):
                        self.payload_for_mqtt.append(list[0])
                        self.counter_for_mqtt = 0

                    if not list[1] is None:
                        if len(list[1]):
                            for i in list[1]:
                                self.payload_for_bacnet[i] = list[1][i]
                                self.counter_for_bacnet = 0

                    self.payload_from_bacnet = []

            if self.counter_for_mqtt == self.config_file_helper.configuration_sending_time_ms:
                self.mqtt_helper.write(self.payload_for_mqtt)
                self.payload_for_mqtt = []

            self.counter_for_mqtt += 1
            self.counter_for_bacnet += 1
            self.counter_for_run += 1

            # Sleep for some time to not eat up CPU cycles
            time.sleep(0.1)

    def trigger_discovery(self):
        topic_number = self.topic_to_send

        if topic_number == 0:
            topic = "discovery/edges/detect"
            self.topic_to_send += 1
        elif topic_number == 1:
            topic = "discovery/devices/detect"
            self.topic_to_send += 1
        elif topic_number == 2:
            topic = "discovery/groups/detect"
            self.topic_to_send += 1
        else:
            topic = "discovery/edges/detect"
            self.topic_to_send = 0

        self.logger.debug(f"Sending init message: {topic_number} | {topic}")
        msg = '{"detect": true}'
        self.client.publish(topic, msg)

    def trigger_light(self):
        if self.topic_to_send_for_light == len(self.gateway.vertex):
            return

        uid = self.gateway.vertex[self.topic_to_send_for_light].id
        topic = f"vertex3/light/{uid}/get_state"
        self.logger.debug(f"Sending init message: {uid} | {topic}")
        msg = '{"detect": true}'
        if self.topic_to_send_for_light < len(self.gateway.vertex):
            self.client.publish(topic, msg)
            self.topic_to_send_for_light += 1
        else:
            self.topic_to_send_for_light = 0

    def on_message(self, client, userdata, message):
        # Parsing, splitting JSON
        try:
            raw_value = message.payload.decode("utf-8")
            if not (len(raw_value)):
                return
            self.logger.debug(f"Receiving messages from topic: {message.topic}")
            josn_value = json.loads(raw_value)
            split_topic = message.topic.split("/")

            # Checking if topic is discovery/edges, if is, do function and finish
            if len(split_topic) == 2 and message.topic == "discovery/edges":
                self.mqtt_helper.edges(josn_value, self.config_file_helper.vertex_uid_vertex,
                                       self.config_file_helper.vertex_max_vertex)
                self.trigger_discovery()
                return

            # Checking if topic is discovery/devices, if is, do function and finish
            if len(split_topic) == 2 and message.topic == "discovery/devices":
                self.mqtt_helper.devices(josn_value)
                self.trigger_discovery()
                return

            # Checking if topic is discovery/groups, if is, do function and finish
            if len(split_topic) == 2 and message.topic == "discovery/groups":
                self.mqtt_helper.groups(josn_value)
                self.topic_to_send += 1
                self.bacnet_helper.create_bacnet_points()
                self.dump_gateway()
                self.trigger_light()
                return

            # Checking if topic is vertex3/light/+/state, if is, do function and finish
            if (len(split_topic) == 4 and split_topic[0] == "vertex3" and split_topic[1] == "light"
                    and split_topic[3] == "state"):
                self.mqtt_helper.all_light(josn_value, self.payload_for_bacnet)
                self.counter_for_bacnet = 0
                self.trigger_light()
                return

            # Checking if topic is vertex3/light/+/+/state, if is, do function and finish
            if (len(split_topic) == 5 and split_topic[0] == "vertex3" and split_topic[1] == "light"
                    and split_topic[4] == "state"):
                self.mqtt_helper.individual_light(split_topic[2], split_topic[3], josn_value,
                                                  self.payload_for_bacnet)
                self.counter_for_bacnet = 0
                return

            # Checking if topic is vertex3/group/+/feedback/state, if is, do function and finish
            if (len(split_topic) == 5 and split_topic[0] == "vertex3" and split_topic[1] == "group"
                    and split_topic[3] == "feedback" and split_topic[4] == "state"):
                self.mqtt_helper.groups_feedback(split_topic[2], josn_value, self.payload_for_bacnet)
                return

            # Checking if topic is "vertex3/sensor/+/+/+/state", if is, do function and finish
            if (len(split_topic) == 6 and split_topic[0] == "vertex3" and split_topic[1] == "sensor"
                    and split_topic[5] == "state"):
                self.mqtt_helper.individual_sensor(split_topic[2], split_topic[3], split_topic[4], josn_value,
                                                   self.payload_for_bacnet)
                self.counter_for_bacnet = 0
                return

            # Checking if topic is "vertex3/button/+/+/+/state", if is, do function and finish
            if (len(split_topic) == 6 and split_topic[0] == "vertex3" and split_topic[1] == "button"
                    and split_topic[5] == "state"):
                self.mqtt_helper.individual_button(split_topic[2], split_topic[3], split_topic[4], josn_value,
                                                   self.payload_for_bacnet)
                self.counter_for_bacnet = 0
                return

        except Exception as error:
            self.logger.error(f"On receiving message | Response parse error - {error}")

    def on_connect(self, client, userdata, flages, rc):
        self.quantity_of_connection_try = 0
        filesource = join(pathfile, 'config\MqttErrorCode.json')
        with open(filesource, encoding='utf-8') as f:
            data = json.loads(f.read())
            self.logger.debug(f"Connected with result: {data[f'{rc}']}")
            self.trigger_discovery()

    def on_disconnect(self, client, userdata, rc):
        filesource = join(pathfile, 'config\MqttErrorCode.json')
        with open(filesource, encoding='utf-8') as f:
            data = json.loads(f.read())
            self.logger.message(f"Disconnected: {data[f'{rc}']}")
            self.reconnect = schedule.every(10).seconds.do(self.reconnect_to_vertex)

    def connect_to_vertex(self):
        """
        Connect to Vertex broker
        """
        quantity_vertex_ip = len(self.config_file_helper.vertex_ip_vertex)

        if not (quantity_vertex_ip > self.vertex_ip_choose_during_reconnect):
            self.vertex_ip_choose_during_reconnect = 0

        ip_choose = self.vertex_ip_choose_during_reconnect
        ip_vertex = self.config_file_helper.vertex_ip_vertex[ip_choose]

        try:
            self.logger.debug(f"Connecting to Vertex on IP: {ip_vertex} in progres")
            self.client.username_pw_set(VERTEX_MQTT_USERNAME, VERTEX_MQTT_PASSWORD)
            self.client.connect(ip_vertex, 1883, self.config_file_helper.vertex_timeout)
            self.client.loop_start()  # start the loop
            self.client.subscribe(self.mqtt_topics)
            self.logger.message(f"✅ Connected to the Vertex device")
            return True
        except:
            self.vertex_ip_choose_during_reconnect += 1
            self.logger.error(f"Connection failed on ip: {ip_vertex}")
            self.logger.debug(f"connect_to_vertex: {schedule.get_jobs('reconnect')}")
            if not len(schedule.get_jobs('reconnect')):
                self.reconnect = schedule.every(10).seconds.do(self.reconnect_to_vertex).tag('reconnect', 'vertex')
            return False

    def reconnect_to_vertex(self):
        self.logger.debug("Another try to connect")
        if self.connect_to_vertex():
            schedule.cancel_job(self.reconnect)
            self.logger.debug(f"reconnect_to_vertex: {schedule.get_jobs('reconnect')}")
            self.logger.debug("Reconnect scheduler task ended")


def parse_command_line_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=f"{INTERFACE_NAME} Module")

    parser.add_argument("--controller", "-c",
                        help="Controller address to read and write data from defaults to local device",
                        default=None, type=int)

    parser.add_argument("--debug", "-d",
                        help="Debug output level 0,1,2,3,4",
                        default=0, const=0, nargs='?', type=int, choices=range(0, 5))

    parser.add_argument("--user", "-u",
                        help="Python user name to login to bnserver",
                        default='Delta')

    parser.add_argument("--password", "-p",
                        help="Python password to login to bnserver",
                        default='Thi#s1sTh3N%wLo1n')

    parser.add_argument("--site", "-s",
                        help="Site to use",
                        default='MainSite')

    return parser.parse_args()


def main():
    args = parse_command_line_args()

    try:
        status = interface_object = Main(
            device=args.controller, username=args.user,
            password=args.password, site=args.site,
            debug=args.debug
        )

        if not status.init_completed:
            interface_object.logger.error("Closing gateway, another try to get setting file after 1 minutes")
            return

        if interface_object.gateway.licenseIsValid():
            interface_object.logger.message("✅ License is valid")
            dev_mode = interface_object.gateway.licenseIsDev()
            if dev_mode:
                interface_object.logger.message("Developer option activated")
            # Start interface should never end
            interface_object.run()
        else:
            interface_object.logger.warn("License is not valid, try another license")
            interface_object.logger.error("Closing gateway, another try to get setting file after 1 minutes")

    except Exception as error:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        filename = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(f"{INTERFACE_NAME} error: {filename}\n{error}")


if __name__ == '__main__':
    main()
