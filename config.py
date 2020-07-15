#!/usr/bin/env python
## -*- python -*-

PATH = './tmp/records/'

STATIONS = {
    # 'szsdr': {
    #     'server_host': 'radiopi.local', 
    #     'server_port': 8073,
    #     'password': 'passwor0d',
    #     'tlimit_password': 'passwor0d',
    #     'callsign': 'BD7MQB',
    #     'grid': 'OL72an',
    # },
    
    # 'czsdr': {
    #     'server_host': 'cz.kiwisdr.go1982.com', 
    #     'server_port': 8073,
    #     'password': 'passwor0d',
    #     'tlimit_password': 'passwor0d',
    #     'callsign': 'BD7MQB-2',
    #     'grid': 'OM88co',
    # },
    
    'cdsdr': {
        'server_host': 'cdkiwisdr.ddns.net', 
        'server_port': 8073,
        'password': 'passwor0d',
        'tlimit_password': 'passwor0d',
        'callsign': 'BD7MQB-3',
        'grid': 'OM10wq',
    },
}

SCHEDULES = {
    '*': {'cdsdr': [20]},
    # '*': {'szsdr': [20,30], 'czsdr': [20,30]},
    # '14:00-17:08': {'szsdr': [40, 20], 'czsdr': [40]},
    # '20:00-20:51': {'szsdr': [20, 60]},
    # '20:51-22:00': {'szsdr': [40, 30, 20], 'czsdr': [20, 40]},
    # '*': {'szsdr': [10, 12, 15, 17, 20, 30, 40, 60, 80, 160]},
    # '21:00-08:00': {'szsdr': [10, 12, 15, 17, 20, 30, 40, 60, 80, 160], 'czsdr': [20, 30, 40, 60, 80, 160]},
    # '08:00-14:30': {'szsdr': [10, 12, 15, 17, 20, 30, 40, 60, 80, 160], 'czsdr': [10, 12, 15, 17, 20, 30]},
    # '14:30-21:00': {'szsdr': [10, 12, 15, 17, 20, 30, 40, 60, 80, 160], 'czsdr': [10, 15, 17, 20, 30, 40]},
}