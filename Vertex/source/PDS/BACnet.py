import bntest
import time
import datetime
from Delta.DeltaEmbedded import BACnetInterface

DT_FORMAT = "%Y/%m/%d/%w %H:%M:%S"
READ_TL_BATCH_SIZE = 100

MANUAL_OVERRIDE_WRITE_PRIORITY = 10


class Interface:
    """
    PDS Wrapper for BACnet functionality & additional functions
    """

    def __init__(self, user, password, site, device=None):
        """
        Initialize the object
        """
        self.__bacnet = BACnetInterface(user=user, password=password, site=site)
        self.__device = device

    ##
    # Custom functions
    ##
    def get_server_address(self):
        """
        Get (this) BACnet Server's Address
        """
        return self.__bacnet.server.sitegetdevicenumber(self.__bacnet.user_key, self.__bacnet.site_name)

    def __get_device_reference(self):
        """
        Load the device reference
        """
        # If a device is provided via the command line, we need to reference the remote device.
        # Otherwise, we can simply reference the local device by getting it the site device number
        # from BNTest
        if self.__device:
            return "{deviceref}.DEV{devicenum}".format(deviceref=self.__device, devicenum=self.__device)
        else:
            return "DEV{devicenum}".format(
                devicenum=self.__bacnet.sitegetdevicenumber(self.__bacnet.user_key, self.__bacnet.site_name)
            )

    def register_alarm_callback(self, callback_function):
        """
        Register for an alarm callback
        """
        self.__bacnet.server.setalarmnotifycallback(callback_function)
        self.__bacnet.server.registerforalarmnotification(self.__bacnet.user_key, self.__bacnet.site_name)

    def register_cov_callback(self, callback_function):
        """
        Register for a COV callback
        """
        self.__bacnet.server.setcovnotificationcallback(callback_function)
        self.__bacnet.server.registerforcovnotification(self.__bacnet.user_key, self.__bacnet.site_name)

    def reconfirm_device(self, device):
        """
        Reconfirms a device
        """
        devref = bntest.creference(self.__bacnet.site_name, device)
        # Confirm the device
        retries = 0
        while retries <= 20:
            try:
                self.__bacnet.server.reconfirmdevice(self.__bacnet.user_key, devref, True)
                if retries >= 5:
                    time.sleep(10)
                break
            except:
                retries += 1

    def send_utc_timesync(self, device, date_time):
        """
        Send a UTC Time Sync based on the provided date_time
        """
        time_date_dict = {
            "Year": int(date_time.strftime("%Y")),
            "Month": int(date_time.strftime("%m")),
            "Day": int(date_time.strftime("%d")),
            "Hour": int(date_time.strftime("%H")),
            "Minute": int(date_time.strftime("%M")),
            "Seconds": int(date_time.strftime("%S")),
            "Hundredths": 0,
            "Weekday": int(date_time.strftime("%w"))
        }

        b_datetime = bntest.ctimedate()
        b_datetime.build(time_date_dict)

        return self.__bacnet.server.sendutctimesync(
            self.__bacnet.user_key, self.__bacnet.site_name, device, b_datetime, True
        )

    def reboot_device(self, device):
        """
        Requests a reboot of a device
        """
        devref = bntest.creference(self.__bacnet.site_name, device)

        self.__bacnet.server.reinitializedevice(self.__bacnet.user_key, devref, bntest.REINITDEV_COLDSTART)

    def read_tl_by_date_range(self, tl_ref, start_date, end_date, type=None):
        """
        Read TL data from a tl_ref between the start and end date and return the data
        """

        if isinstance(type, str):
            type = [type]

        tl_data = list()
        exceeded_end = False

        while True:
            c_ref = bntest.creference()
            tl_ref_buffer = self.__fill_in_reference(tl_ref + ".Log_Buffer")

            c_ref.parsereference(
                "//{site}/{ref_prop}".format(site=self.__bacnet.site_name, ref_prop=tl_ref_buffer),
                bntest.LANGUAGE_ID_ENGLISH,
                self.__bacnet.user_key
            )

            data = self.__get_tl_batch(c_ref, start_date)

            if len(data) == 0:
                # No data
                break

            # Iterate over the data, checking types as needed
            for item in data:
                # Update our start date
                start_date = item[0]

                # Skip if it's not in our type filter
                if type and item[1] not in type:
                    continue

                # Check if we're past our end date
                if item[0] > end_date:
                    exceeded_end = True
                    break

                # If it's a valid type and within our range, add it to our tl_data
                tl_data.append(item)

            if exceeded_end:
                # We've gone past our requested "end date"
                break

            if len(data) != READ_TL_BATCH_SIZE:
                # Read less than the batch size, so we must be at the "end" of the data
                break

        return tl_data

    def __get_tl_batch(self, c_ref, start_dt, batch_size=READ_TL_BATCH_SIZE):
        """
        Get a batch of TL records
        """

        start_ctimedate = bntest.ctimedate()
        start_ctimedate.build({
            "Year": int(start_dt.strftime("%Y")),
            "Month": int(start_dt.strftime("%m")),
            "Day": int(start_dt.strftime("%d")),
            "Hour": int(start_dt.strftime("%H")),
            "Minute": int(start_dt.strftime("%M")),
            "Seconds": int(start_dt.strftime("%S")),
            "Hundredths": 0,
            "Weekday": int(start_dt.strftime("%w"))
        })

        prop_list = bntest.cpropertylist()
        prop_list.addrangebytime(c_ref, start_ctimedate, batch_size)

        self.__bacnet.server.executeobjectrequest(self.__bacnet.user_key, bntest.OBJECT_READ, prop_list)

        data = list()

        prop_list.rewind()
        status = prop_list.getitemstatus()
        if status != "OK":
            raise Exception("{sts} returned from read_range_by_date_range".format(sts=status))
        if not (str(prop_list) == "" or prop_list == None):
            count = prop_list.getarraycount()
            for idx in range(0, count):
                prop_list.nextarrayitem()
                status = prop_list.getitemstatus()
                if status != "OK":
                    raise Exception("{sts} returned from read_range_by_date_range".format(sts=status))
                else:
                    data.append(self.__read_tl_buffer_value(prop_list, c_ref))

        return data

    def __read_tl_buffer_value(self, prop_list, obj_ref):
        """
        Read a TL buffer value
        """
        # Buffer.Timestamp
        obj_ref.setpropertybyname("timestamp", bntest.LANGUAGE_ID_ENGLISH, 1)
        # Split out timestamp
        timestamp = bntest.ctimedate(prop_list.readitem(obj_ref, bntest.LANGUAGE_ID_ENGLISH)).split()

        dt = datetime.datetime(
            year=timestamp['Year'], month=timestamp['Month'], day=timestamp['Day'],
            hour=timestamp['Hour'], minute=timestamp['Minute'], second=timestamp['Seconds']
        )

        # Buffer.Present_Value
        obj_ref.setpropertybyname("logDatum", bntest.LANGUAGE_ID_ENGLISH, 1)
        variant = prop_list.getvariant(obj_ref)
        obj_ref.setpropertybyid(variant, 2)

        type = obj_ref.getpropertyname(bntest.LANGUAGE_ID_ENGLISH, 2)
        if type == "failure":
            # error variant has both code and class properties
            obj_ref.setpropertybyname("class", bntest.LANGUAGE_ID_ENGLISH, 3)
            err_class = prop_list.readitem(obj_ref, bntest.LANGUAGE_ID_ENGLISH)
            obj_ref.setpropertybyname("code", bntest.LANGUAGE_ID_ENGLISH, 3)
            err_code = prop_list.readitem(obj_ref, bntest.LANGUAGE_ID_ENGLISH)
            value = err_class + ":" + err_code
        else:
            # other variants can simply be read
            value = prop_list.readitem(obj_ref, bntest.LANGUAGE_ID_ENGLISH)

        return dt, type, value

    ##
    # Wrapper Functions
    ##

    def write(self, data, priority=MANUAL_OVERRIDE_WRITE_PRIORITY, request_type=bntest.OBJECT_WRITE):
        """
        Send write request.
        Can handle multiple and complex properties.

        @param data: Dictionary of data to be sent in the write request
                     Should be in format: {<Property>:<Value>, ...}
                     <Value> can be a string (for simple properties), a list of strings (for array or list properties),
                     or a dictionary of the same format (for complex properties or properties with subproperties).

                        Examples:
                            Simple Property:         write({'4000.AV1.Name': 'New AV Name'})
                            Array Property:          write({'300.AI4.EventText': ['Text1', 'Text2', 'Text3']})
                            Complex Property:        write({'5000.SCH1.DefaultValue.Real' : '5',
                                                                '5000.SCH1.ExceptionsExt[1]' : {
                                                                    'Schedule[1].Time': '08:00:00.00',
                                                                    'Schedule[1].Value.Real': '5',
                                                                    'Schedule[2].Time': '017:30:00.00',
                                                                    'Schedule[2].Value.Null': '',
                                                                    'Period.CalendarEntry.WeekNDay.Week': '4',
                                                                    'Period.CalendarEntry.WeekNDay.WDay': '5',
                                                                    'Period.CalendarEntry.WeekNDay.Month': '6',
                                                                    'EventPriority': '8',
                                                                            'Description': 'Test Week and Day!'}})
                                            Or this could be written with:
                                                     write({'5000.SCH1.DefaultValue.Real' : '5',
                                                                '5000.SCH1.ExceptionsExt[1]' : {
                                                                'Schedule': [{'Time': '08:00:00.00', 'Value.Real': '5'},
                                                                             {'Time': '017:30:00.00', 'Value.Null': ''}]
                                                                'Period.CalenderEntry.WeekNDay': {
                                                                    'Week': '4',
                                                                    'WDay': '5',
                                                                    'Month': '6'}
                                                                'EventPriority': '8',
                                                                'Description': 'Test Week and Day!' }})
        @param priority: (Optional) write priority
        @param request_type: (Optional) Can be set to OBJECT_CREATE to write data as a create object request.
        @returns: status of property list
        """
        # Add device if one is provided
        if self.__device:
            tmp_dict = dict()
            for key, value in data.items():
                tmp_dict[f"{self.__device}.{key}"] = value
            data = tmp_dict

        return self.__bacnet.write(data, priority, request_type)

    def write_value(self, reference, value):
        """
        Perform a write for a single
        """
        if self.__device:
            reference = f"{self.__device}.{reference}"

        return self.__bacnet.write_value(reference, value)

    def read(self, property_references):
        """Perform a read and set the results in a dictionary.
        Can read multiple and complex (properties with subproperties) references

        @param References: list of references to read
        @returns: ReadResults dictionary object
        """
        # Add device if one is provided
        if self.__device:
            tmp_list = list()
            for reference in property_references:
                tmp_list.append(f"{self.__device}.{reference}")
            property_references = tmp_list

        return self.__bacnet.read(property_references)

    def read_value(self, property_reference):
        """
        Perform a read of a single property and return value
        """
        if self.__device:
            property_reference = f"{self.__device}.{property_reference}"
        return self.__bacnet.read_value(property_reference)

    def find_object_by_name(self, obj_name=None, obj_type=None, device=None):
        """
        Given a specific name find the object with that name and return the reference.

        :param obj_name: String the name of the object to find
        :param obj_type: String the acronym of the object to find (blank for any type)
        :param device: Device number to search on (blank for any type)
        :return: String the reference or None if not found
        """
        if device is None:
            return self.__bacnet.find_object_by_name(obj_name, obj_type)
        else:
            return self.__bacnet.find_object_by_name(obj_name, obj_type, device)

    def get_next_free_obj_instance(self, obj_type, device=None):
        """
        Given a specific object type, find the next free object instance

        :param obj_type: The BACnet object type (ex: "CSV")
        :param device: Device number to search on (blank for any type)

        :return: string
        """
        return self.__bacnet.get_next_free_obj_instance(obj_type, device)

    def __fill_in_reference(self, reference):
        """Fill in any missing info in a property reference
        Add device if it is not specified
        Add object instance for DEV or DBI if it is not specified
        """
        local_device = self.get_server_address()

        # check for missing device
        if not reference.split('.')[0].isdigit():
            reference = str(local_device) + '.' + reference

        # check for missing object instance
        dev, obj, prop = reference.split(".", 2)
        if obj.lower() in ('dev', 'dbi'):
            obj = obj + str(local_device)

        return '.'.join([dev, obj, prop])

    def find_object_by_id(self, object_id, device=None):
        if device is None:
            return self.__bacnet.find_object_by_id(object_id, self.__device)
        else:
            return self.__bacnet.find_object_by_id(object_id, device)
