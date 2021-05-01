''' Taking ths influx logging concepts from the Bridge container from https://github.com/Nilhcem/home-monitoring-grafana
    but going directly from the Skyport JSON object into Influx to avoid some data type mangling (and the overhead of 
    making the extra hop through MQTT). Also adding the ability to set some ignore filters so that it doesn't dump a bunch
    of useless P1P2 or S21 bus data into the database if you've got a unitary system that doesn't use it. '''

import logging
import os
from datetime import timedelta
from influxdb import InfluxDBClient
import json
import six
import crython

from daikinskyport import DaikinSkyport

with open('config.json') as f:
    config = json.load(f)

skyport = DaikinSkyport(None, config['SKYPORT_EMAIL'], config['SKYPORT_PASSWORD'])
influxdb_client = InfluxDBClient(config['INFLUXDB_ADDRESS'], 8086, config['INFLUXDB_USER'], config['INFLUXDB_PASSWORD'], None)

@crython.job(second=range(0, 60, 30))
def doUpdate():
    skyport.update()
    print(skyport.thermostatlist)
    for thermostat in skyport.thermostatlist: #should just be the one
        thermoData = skyport.get_thermostat_info(thermostat['id'])
        print(thermoData)

def _init_influxdb_database():
    databases = influxdb_client.get_list_database()
    if len(list(filter(lambda x: x['name'] == config['INFLUXDB_DATABASE'], databases))) == 0:
        influxdb_client.create_database(config['INFLUXDB_DATABASE'])
    influxdb_client.switch_database(INFLUXDB_DATABASE)
        

if __name__ == '__main__':



    crython.start()
    crython.join()  ## This will block
