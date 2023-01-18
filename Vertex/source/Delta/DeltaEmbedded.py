import bntest
from types import *
import re
import datetime
import random
import os

from Delta import Results

server = None 

class BACnetInterface(object):

    def __init__(self, user="Admin", password="AdminBMS", site="Techniczny"):
        global server
        if not server:
            server = bntest.cserver()
            server.connect(monitored=False)
        self.server = server 
        #print("User: {}".format(user))
        #print("Pass: {}".format(password))
        #print("Site: {}".format(site))
        
        self.user_key = self.server.login(user, password)

        self.site_name = site
        if self.site_name not in self.server.sitegetlist(self.user_key):
            raise RuntimeError("Site {name} does not exist".format(name=self.site_name))

        if not self.server.siteisopen(self.user_key, self.site_name):
            self.server.siteopen(self.user_key, self.site_name)


    def __fill_in_reference(self, reference):
        """Fill in any missing info in a property reference
        Add device if it is not specified
        Add object instance for DEV or DBI if it is not specified
        """
        local_device = self.server.setupgetparameter(self.user_key, self.site_name, "CFG_SITE_DEVICENUMBER", 0)

        # check for missing device
        if not reference.split('.')[0].isdigit():
            reference = str(local_device) + '.' + reference

        # check for missing object instance
        dev, obj, prop = reference.split(".", 2)
        if obj.lower() in ('dev', 'dbi'):
            obj = obj + str(local_device)

        return '.'.join([dev, obj, prop])

    def split_reference(self, reference):
        """
        Extract components of a reference string.
        
        @returns: dict with value for each component found in the reference
            ex:
                split_reference("//MainSite/1234.av56.description")
                    {'Site' : 'MainSite', 'Device': '1234', 'Object Type': 'av', 'Object Instance': 56, 'Property Reference': 'description'}
                split_reference("av56")
                    {'Object Type': 'av', 'Object Instance': 56}
        """
        return bntest.creference().splitreference(reference)

    def read(self, property_references):
        """Perform a read and set the results in a dictionary.
        Can read multiple and complex (properties with subproperties) references

        @param References: list of references to read
        @returns: ReadResults dictionary object
        """
        try:
            basestring
        except NameError:
            basestring = str

        if isinstance(property_references, basestring):
            refs = [self.__fill_in_reference(property_references)]
        else:
            refs = [self.__fill_in_reference(ref) for ref in property_references]

        prop_list = bntest.cpropertylist()
        obj_ref = bntest.creference()

        for ref in refs:
            obj_ref.parsereference(
                    '//{site}/{obj_and_prop}'.format(site=self.site_name, obj_and_prop=ref),
                    bntest.LANGUAGE_ID_ENGLISH,
                    self.user_key)
            prop_list.addreference(obj_ref)
        
        self.server.executeobjectrequest(self.user_key, bntest.OBJECT_READ, prop_list)
        status = prop_list.getpropertyliststatus()

        if status != 'OK':
            raise RuntimeError("Read Error: {code}".format(code=str(status)))

        return Results.ReadResults(prop_list)

    def read_value(self, property_reference):
        """Perform a read of a single property and return value"""
        full_reference = self.__fill_in_reference(property_reference)
        value = self.read(full_reference)
        return value[full_reference]

    def __add_data_to_proplist(self, reference, data_obj, prop_list, priority=bntest.PRIORITY_DEFAULT):
        """Setup proplist for writing.
        Should not be called directly, helper for write().

        @param reference:  creference to base property.
                           if this is a single property, it is added to the propertylist
                           if there are subproperties, each will be recursively added to the propertylist
        @param data_obj: Can be a string, a list of strings, or a dictionary of subproperties and values
        @param prop_list: the cpropertylist to which the references and data is added
        """
        if isinstance(data_obj, list):
            array_index = 1

            if len(data_obj) == 0:
                obj_ref = bntest.creference()
                obj_ref.parsereference(reference, bntest.LANGUAGE_ID_ENGLISH, self.user_key)
                if obj_ref.isarrayproperty():
                    self.__add_data_to_proplist('%s[0]' % reference, '0', prop_list)
                elif obj_ref.islistproperty():
                    try:
                        prop_list.finditem(obj_ref)
                    except:
                        prop_list.addreference(obj_ref)
                    prop_list.setarraycount(obj_ref, 0)
                else:
                    raise('List data specified for non-Array non-List property.')

            for sub_data in data_obj:
                self.__add_data_to_proplist('%s[%i]' %(reference, array_index), sub_data, prop_list)
                array_index += 1
            return

        elif isinstance(data_obj, dict):
            # add dictionary entries in sorted order to ensure array indices specified in the references are added in the correct order
            for sub_property in sorted(data_obj.keys(), key=lambda s: s.lower()):
                sub_data = data_obj[sub_property]

                if reference.endswith('/'):
                    full_ref = reference + sub_property
                else:
                    full_ref = reference + '.' + sub_property
                self.__add_data_to_proplist(full_ref, sub_data, prop_list, priority=priority)
            return

        else:
            if isinstance(data_obj, (str, bntest.ctext, type(None))):
                data = data_obj
            else:
                data = str(data_obj)

            obj_ref = bntest.creference()
            obj_ref.parsereference(reference, bntest.LANGUAGE_ID_ENGLISH, self.user_key)

            top_ref = bntest.creference()
            top_ref.parsereference(reference, bntest.LANGUAGE_ID_ENGLISH, self.user_key)
            top_ref.setdepth(0)
            temp_ref = bntest.creference()

            if top_ref.islistproperty():
                list_index = top_ref.getarrayindex()
                top_ref.setarrayindex(bntest.WILD_ARRAY_INDEX)
            try:
                prop_list.finditem(top_ref)
            except:
                # Add the base level property if it's not already in the property list
                prop_list.addreference(top_ref)
            if prop_list.islistitem():
                if prop_list.getarraycount() < list_index:
                    prop_list.setarraycount(None, list_index)
                top_ref.setarrayindex(list_index)
                prop_list.finditem(top_ref)

            # Ensure that array counts are set and that the top level array position is correct
            depth = obj_ref.getdepth()
            # Advance the properties and sub-properties of the full reference
            for curr_depth in range(0, depth + 1):
                temp_ref.parsereference(reference, bntest.LANGUAGE_ID_ENGLISH, self.user_key)
                temp_ref.setdepth(curr_depth)
                if temp_ref.islistproperty():
                    break
                # Is this (sub-)property an array or a list?
                if (
                    temp_ref.isarrayorlistproperty()
                    and obj_ref.getarrayindex() != 0
                    and not top_ref.isfixedarray()
                ):
                    # Increment array count in the proplist
                    array_ref = bntest.creference()
                    array_ref.parsereference(
                        str(temp_ref),
                        bntest.LANGUAGE_ID_ENGLISH,
                        self.user_key
                    )

                    try:
                        prop_list.finditem(temp_ref)
                    except:
                        prop_list.addreference(temp_ref)

            prop_list.modifyitem(obj_ref, data, bntest.LANGUAGE_ID_ENGLISH)
            prop_list.setitempriority(priority)

            return


    def write(self, data, priority=bntest.PRIORITY_DEFAULT, request_type=bntest.OBJECT_WRITE):
        """Send write request.
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

        prop_list = bntest.cpropertylist()
        base_ref = '//{site}/'.format(site=self.site_name)

        for top_level_ref, top_level_data in data.items():
            self.__add_data_to_proplist(
                '//{site}/{ref}'.format(site=self.site_name, ref=self.__fill_in_reference(top_level_ref)),
                top_level_data,
                prop_list,
                priority=priority,
            )

        self.server.executeobjectrequest(self.user_key, request_type, prop_list)
        prop_list.rewind()

        return Results.WriteResults(prop_list)


    def write_value(self, reference, value):
        """Perform a write for a single property"""
        return self.write({reference : value})

    def find_object_by_name(self, obj_name=None, obj_type=None, device=None):
        """
        Given a specific name find the object with that name and return the reference.

        :param obj_name: String the name of the object to find
        :param obj_type: String the acronym of the object to find (blank for any type)
        :param device: Device number to search on (blank for any type)
        :return: String the reference or None if not found
        """

        if obj_name is None:
            return None
        if obj_type is None:
            obj_type = ""

        try:

            objReference = bntest.creference()

            if device is None:
                device = self.server.sitegetdevicenumber(self.user_key, self.site_name)

            wildReference = bntest.cwildreference(self.site_name, int(device), bntest.WILD_OBJECT_INSTANCE, obj_type)

            search = bntest.cdescriptorsearch(self.user_key, obj_name, wildReference)

            found = search.first(objReference)
            if found is None:
                return None

            search.complete()

            value = ("{type}{instance}".format(type=objReference.getobjecttypeabbr(bntest.LANGUAGE_ID_ENGLISH),
                                               instance=objReference.getobjectinstance()))

        except Exception as error:
            raise Exception("Find Object: {error}".format(error=error))

        return value

    def find_object_by_id(self, object_id, device=None):
        """Given an object id find and return the object's name.
        If the object does not exist return None.
        """
        if device is None:
            device = self.server.sitegetdevicenumber(self.user_key, self.site_name)
        full_ref_text = f"//{self.site_name}/{int(device)}.{object_id}"
        object_ref = bntest.creference(full_ref_text, bntest.LANGUAGE_ID_ENGLISH, self.user_key)
        try:
            object_name = self.server.findname(self.user_key, object_ref)
            return object_name 
        except Exception as e:
            if str(e) == "QERR_CLASS_OS::QERR_CODE_NOTFOUND":
                return None 
            else:
                # unexpected error, throw it up
                raise(e)


if __name__ == '__main__':
    bacnet = BACnetInterface()


