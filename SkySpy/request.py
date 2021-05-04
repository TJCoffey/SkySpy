''' Taking ths influx logging concepts from the Bridge container from https://github.com/Nilhcem/home-monitoring-grafana
    but going directly from the Skyport JSON object into Influx to avoid some data type mangling (and the overhead of 
    making the extra hop through MQTT). Also adding the ability to set some ignore filters so that it doesn't dump a bunch
    of useless P1P2 or S21 bus data into the database if you've got a unitary system that doesn't use it. '''

import os
from influxdb import InfluxDBClient
import json
import six
import crython
import re

from daikinskyport import DaikinSkyport

with open('config.json') as f:
	config = json.load(f)

influxdb_client = InfluxDBClient(config['INFLUXDB_ADDRESS'], 8086, config['INFLUXDB_USER'], config['INFLUXDB_PASSWORD'], None)
skyport = DaikinSkyport(None, config['SKYPORT_EMAIL'], config['SKYPORT_PASSWORD'])
categoryRegExes = []
ignoreRegExes = []

@crython.job(second=range(0, 60, 30))
def doUpdate():
    skyport.update()
    for thermostat in skyport.thermostatlist:
        thermoData = skyport.get_thermostat_info(thermostat['id'])
        processDataObject(thermostat, thermoData)

def _init_influxdb_database():
    databases = influxdb_client.get_list_database()
    if len(list(filter(lambda x: x['name'] == config['INFLUXDB_DATABASE'], databases))) == 0:
        influxdb_client.create_database(config['INFLUXDB_DATABASE'])
    influxdb_client.switch_database(config['INFLUXDB_DATABASE'])

def getCategory(param):
	for category in categoryRegExes:
		if category[0].match(param):
			return category[1]
	return None

def processParameter(param, thermoData, thermostat):
	#First check is to see if we should be ignoring it
	for ignore in ignoreRegExes:
		if ignore.match(param):
			return None
	#If we're still here, we've got a parameter to work with
	rtn = {
		'measurement': param,
        'tags': {
            'location': thermostat['name']
        },
        'fields': {
            'value': thermoData[param]
        }
	}
	category = getCategory(param)
	if category != None:
		rtn['tags']['category'] = category
	return rtn

def processDataObject(thermostat, thermoData):
	#Array of JSON objects to pass to write_points. TODO: Look at perf and see if we want to directly make line format
	json_body = []
	point = None

	#Iterate the parameter list
	for param in thermoData:
		point = processParameter(param, thermoData, thermostat)
		if point != None:
			json_body.append(point)
	influxdb_client.write_points(json_body)

def setup():

	_init_influxdb_database()

	# Build regexes for our Category tag prefixes
	for category in config['CATEGORY_PREFIXES']:
		categoryRegExes.append([re.compile('^' + category), config['CATEGORY_PREFIXES'][category]])

	# Build regexes for our ignored tag prefixes
	for prefix in config['IGNORED_PREFIXES']:
		ignoreRegExes.append(re.compile('^' + prefix))

if __name__ == '__main__':
	setup()
	crython.start()
	crython.join()  ## This will block