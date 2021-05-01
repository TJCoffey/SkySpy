''' Python Code for Communication with the Daikin Skyport Thermostat. This is a modified version of the apetrycki/daikinskyport homeassistant integration on GitHub
    which was taken mostly from pyecobee, so much credit to those contributors'''
import requests
import json
import os
import logging

from requests.exceptions import RequestException

logger = logging.getLogger('daikinskyport')

def config_from_file(filename, config=None):
    ''' Small configuration file management function'''
    if config:
        # We're writing configuration
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            logger.exception(error)
            return False
        return True
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                return False
        else:
            return {}


class DaikinSkyport(object):
    ''' Class for storing Daikin Skyport Thermostats and Sensors '''

    def __init__(self, config_filename=None, user_email=None, user_password=None, config=None):
        self.thermostats = list()
        self.thermostatlist = list()
        self.authenticated = False

        if config is None:
            self.file_based_config = True
            if config_filename is None:
                if (user_email is None) or (user_password is None):
                    logger.error("Error. No user email or password was supplied.")
                    return
                jsonconfig = {"EMAIL": user_email, "PASSWORD": user_password}
                config_filename = 'daikinskyport.conf'
                config_from_file(config_filename, jsonconfig)
            config = config_from_file(config_filename)
        else:
            self.file_based_config = False
        if 'EMAIL' in config:
            self.user_email = config['EMAIL']
        else:
            logger.error("Email missing from config.")
        if 'PASSWORD' in config: # PASSWORD is only needed during first login
            self.user_password = config['PASSWORD']
        self.config_filename = config_filename

        if 'ACCESS_TOKEN' in config:
            self.access_token = config['ACCESS_TOKEN']
        else:
            self.access_token = ''

        if 'REFRESH_TOKEN' in config:
            self.refresh_token = config['REFRESH_TOKEN']
        else:
            self.refresh_token = ''
            self.request_tokens()
            return

        self.update()

    def request_tokens(self):
        ''' Method to request API tokens from skyport '''
        url = 'https://api.daikinskyport.com/users/auth/login'
        header = {'Accept': 'application/json',
                  'Content-Type': 'application/json'}
        data = {"email": self.user_email, "password": self.user_password}
        try:
            request = requests.post(url, headers=header, json=data)
        except RequestException:
            logger.warn("Error connecting to Daikin Skyport.  Possible connectivity outage."
                        "Could not request token.")
            return
        if request.status_code == requests.codes.ok:
            self.access_token = request.json()['accessToken']
            self.refresh_token = request.json()['refreshToken']
            if self.refresh_token is None:
                logger.error("Auth did not return a refresh token.")
            else:
                self.write_tokens_to_file()
        else:
            logger.warn('Error while requesting tokens from daikinskyport.com.'
                        ' Status code: ' + str(request.status_code))
            return

    def refresh_tokens(self):
        ''' Method to refresh API tokens from daikinskyport.com '''
        url = 'https://api.daikinskyport.com/users/auth/token'
        header = {'Accept': 'application/json',
                  'Content-Type': 'application/json'}
        data = {'email': self.user_email,
                  'refreshToken': self.refresh_token}
        request = requests.post(url, headers=header, json=data)
        if request.status_code == requests.codes.ok:
            self.access_token = request.json()['accessToken']
            self.write_tokens_to_file()
            return True
        else:
            self.request_tokens()

    def get_thermostats(self):
        ''' Set self.thermostats to a json list of thermostats from daikinskyport.com '''
        url = 'https://api.daikinskyport.com/devices'
        header = {'Content-Type': 'application/json;charset=UTF-8',
                  'Authorization': 'Bearer ' + self.access_token}
        try:
            request = requests.get(url, headers=header)
        except RequestException:
            logger.warn("Error connecting to Daikin Skyport.  Possible connectivity outage.")
            return None
        if request.status_code == requests.codes.ok:
            self.authenticated = True
            self.thermostatlist = request.json()
            for thermostat in self.thermostatlist:
                overwrite = False
                thermostat_info = self.get_thermostat_info(thermostat['id'])
                thermostat_info['name'] = thermostat['name']
                thermostat_info['id'] = thermostat['id']
                for index in range(len(self.thermostats)):
                    if thermostat['id'] == self.thermostats[index]['id']:
                        overwrite = True
                        self.thermostats[index] = thermostat_info
                if not overwrite:
                    self.thermostats.append(thermostat_info)
            return self.thermostats
        else:
            self.authenticated = False
            logger.info("Error connecting to Daikin Skyport while attempting to get "
                        "thermostat data.  Refreshing tokens and trying again.")
            if self.refresh_tokens():
                return self.get_thermostats()
            else:
                return None

    def get_thermostat_info(self, deviceid):
        ''' Retrieve the device info for the specific device '''
        url = 'https://api.daikinskyport.com/deviceData/' + deviceid
        header = {'Content-Type': 'application/json;charset=UTF-8',
                  'Authorization': 'Bearer ' + self.access_token}
        try:
            request = requests.get(url, headers=header)
        except RequestException:
            logger.warn("Error connecting to Daikin Skyport.  Possible connectivity outage.")
            return None
        if request.status_code == requests.codes.ok:
            self.authenticated = True
            return request.json()
        else:
            self.authenticated = False
            logger.info("Error connecting to Daikin Skyport while attempting to get "
                        "thermostat data.  Refreshing tokens and trying again.")
            if self.refresh_tokens():
                return self.get_thermostat_info()
            else:
                return None

    def get_thermostat(self, index):
        ''' Return a single thermostat based on index '''
        return self.thermostats[index]

    def write_tokens_to_file(self):
        ''' Write api tokens to a file '''
        config = dict()
        config['ACCESS_TOKEN'] = self.access_token
        config['REFRESH_TOKEN'] = self.refresh_token
        config['EMAIL'] = self.user_email
        if self.file_based_config:
            config_from_file(self.config_filename, config)
        else:
            self.config = config

    def update(self):
        ''' Get new thermostat data from daikin skyport '''
        self.get_thermostats()

    def make_request(self, index, body, log_msg_action, *, retry_count=0):
        deviceID = self.thermostats[index]['id']
        url = 'https://api.daikinskyport.com/deviceData/' + deviceID
        header = {'Content-Type': 'application/json;charset=UTF-8',
                  'Authorization': 'Bearer ' + self.access_token}
        logger.error("Make Request: Device: %s, Body: %s", deviceID, body)
        try:
            request = requests.put(url, headers=header, json=body)
        except RequestException:
            logger.warn("Error connecting to Daikin Skyport.  Possible connectivity outage.")
            return None
        if request.status_code == requests.codes.ok:
            return request
        elif (request.status_code == 401 and retry_count == 0 and
              request.json()['error'] == 'authorization_expired'):
            if self.refresh_tokens():
                return self.make_request(body, deviceID, log_msg_action,
                                         retry_count=retry_count + 1)
        else:
            logger.warn(
                "Error fetching data from Daikin Skyport while attempting to %s: %s",
                log_msg_action, request.json())
            return None