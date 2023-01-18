"""

"""
import json
import bntest
from PDS.Config import CSVConfigManager


class ConfigFileHelper:

    def __init__(self, settings_file_name, bacnet, logger, device):

        self.dev_mode = False
        self.settings_file_name = settings_file_name
        self.bacnet = bacnet
        self.logger = logger
        self.device = device
        self.config = CSVConfigManager(self.bacnet, self.logger, self.device)
        self.cfg = None

        self.configuration_license = None
        self.configuration_use_tags = None
        self.configuration_use_auto_create = None
        self.configuration_rename_with_port_and_short_address = None
        self.configuration_setting_file_refresh = None
        self.configuration_sending_time_ms = None
        self.vertex_ip_vertex = []
        self.vertex_uid_vertex = []
        self.vertex_max_vertex = None
        self.vertex_max_bacnet_points = None
        self.vertex_timeout = None

        configuration_dict = {
            "license": "",
            "use_auto_create": True,
            "rename_with_port_and_short_address": True,
            "debug": 0
        }
        vertex_ip_config = ["0.0.0.0", "0.0.0.1"]
        vertex_uid_custom = ["B827EB0C25C4"]
        vertex_dict = {
            "ip_address": vertex_ip_config,
            "uid_vertex": vertex_uid_custom
        }
        default_settings_file = {
            "configuration": configuration_dict,
            "vertex": vertex_dict
        }
        try:
            settings_file_instance = self.bacnet.find_object_by_name(f'{self.settings_file_name}', obj_type="CSV",
                                                                     device=self.device)
            if settings_file_instance is None:
                generate_status = self.bacnet.write({'CSV3900000.Name': f'{self.settings_file_name}',
                                                     'CSV3900000.Relinquish_Default': json.dumps(
                                                         default_settings_file)},
                                                    request_type=bntest.OBJECT_CREATE)
                self.logger.message(f"✅ Settings file generate - {list(generate_status.items())[0][1]}")
        except Exception as error:
            self.logger.error(f"ConfigFileHelper|52 {error}")

    def addConfig(self):
        try:
            self.config.add(self.settings_file_name, self.configReader)
        except Exception as error:
            if error == f"Configuration object {self.settings_file_name} could not be found":
                self.logger.error(error)
                return False
            if error == f"Configuration object {self.settings_file_name} was empty":
                self.logger.error(error)
                return False
            self.logger.error(f"ConfigFileHelper|64 {error}")
            return False
        return True

    def getConfig(self):
        try:
            self.cfg = self.config.get(self.settings_file_name)
            try:
                # TODO Jesli sie zmieni i jest nie wazna to disconect mqtt i stop run proces
                self.configuration_license = self.cfg['configuration']['license']
            except:
                self.configuration_license = ""
            try:
                tmp = self.cfg['configuration']['debug']
                self.logger.set_level(tmp)
                if not tmp:
                    self.logger.warn("Disabling debugging")
            except:
                self.logger.warn("Disabling debugging")
                self.logger.set_level(0)
            try:
                self.vertex_ip_vertex = self.cfg['vertex']['ip_address']
            except:
                self.vertex_ip_vertex = []
            try:
                self.vertex_uid_vertex = self.cfg['vertex']['uid_vertex']
            except:
                self.vertex_uid_vertex = []
            try:
                self.configuration_use_auto_create = bool(self.cfg['configuration']['use_auto_create'])
            except:
                self.configuration_use_auto_create = False
            try:
                self.configuration_rename_with_port_and_short_address = bool(
                    self.cfg['configuration']['rename_with_port_and_short_address'])
            except:
                self.configuration_rename_with_port_and_short_address = False

            # For developer purposes
            if self.dev_mode:
                try:
                    self.configuration_use_tags = bool(self.cfg['configuration']['use_tags'])
                except:
                    self.configuration_use_tags = False
                try:
                    self.configuration_setting_file_refresh = self.cfg['configuration']['setting_file_refresh']
                except:
                    self.configuration_setting_file_refresh = 20
                try:
                    self.configuration_sending_time_ms = self.cfg['configuration']['sending_time_ms']
                except:
                    self.configuration_sending_time_ms = 3
                try:
                    self.vertex_max_vertex = self.cfg['vertex']['max_vertex']
                except:
                    self.vertex_max_vertex = 10
                try:
                    self.vertex_max_bacnet_points = self.cfg['vertex']['max_bacnet_points']
                except:
                    self.vertex_max_bacnet_points = 999
                try:
                    self.vertex_timeout = self.cfg['vertex']['timeout']
                except:
                    self.vertex_timeout = 60
            else:
                self.configuration_use_tags = False
                self.configuration_setting_file_refresh = 20
                self.vertex_max_vertex = 10
                self.vertex_max_bacnet_points = 999
                self.vertex_timeout = 60
                self.configuration_sending_time_ms = 3

        except Exception as error:
            self.logger.error(error)
            return False
        return True

    def configReader(self):
        self.getConfig()

    def check_all_for_update(self):
        self.config.check_all_for_update()
