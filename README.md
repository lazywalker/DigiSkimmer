# DigiSkimmer - FT8/FT4/WSPR skimmer base on kiwirecorder/KiwiSDR
The idea was learned from [wsprdaemon](https://raw.githubusercontent.com/rrobinett/wsprdaemon), yet FT8 mode is more and more popular nowdays, more signals, easer to pickup(compared to wspr, some people use maga watt to transmit FT8). 

This can be useful in determining propagation conditions or in adjusting antenna. A wide band antenna kiwisdr located in urban area in my case, with 10 bands requests at the same time, can be easily reach over 10,000 spots within 24 hours.

It is also interesting to see how long it takes to spot 100 different DXCC/countries. (A well placed station with a decent antenna can do this within a week of monitoring, but the best systems can do it within a single day).

This is a console application and it looks just like:
```log
2020-12-12 17:59:32,847 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB3.0 DT1.9 F7.075188 BG5USO HL5FAM R-17 : -
2020-12-12 17:59:32,847 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB-2.0 DT0.5 F7.075102 YD1ELG DS1AAK -20 : -
2020-12-12 17:59:32,847 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB-14.0 DT0.5 F7.074700 7C9T JA1FJJ -09 : -
2020-12-12 17:59:32,847 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB-2.0 DT0.4 F7.076949 <...> JA1JAN -10 : -
2020-12-12 17:59:32,847 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB-14.0 DT0.7 F7.074592 CQ BH6ODC OM64 : BH6ODC OM64
2020-12-12 17:59:32,848 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB-13.0 DT0.7 F7.074650 CQ DS2CXN PM37 : DS2CXN PM37
2020-12-12 17:59:32,848 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB-21.0 DT0.5 F7.076006 CQ JH4BTI PM54 : JH4BTI PM54
2020-12-12 17:59:32,848 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB-16.0 DT0.4 F7.074667 HS0ZMB 6K2KQW PM37 : 6K2KQW PM37
2020-12-12 17:59:32,848 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB-22.0 DT-0.4 F7.074313 BI4XYB UN7ECA MO52 : UN7ECA MO52
2020-12-12 17:59:32,848 INFO  3677478 [QW-1] [czsdr] FT8 T175915 DB-19.0 DT0.5 F7.075615 RW4CCW JA1VVX PM95 : JA1VVX PM95
 -[T:33 Q:13] FT8:[##........]  FT4:[####......]        WSPR:[#######...]
      \                  \               |                \
Time&Queue indicator  FT8 progress   FT4 progress       WSPR progress
```

# Getting Started using Docker / Podman
If you have a running docker setup you should quite easy to get started.
```bash
docker run -eTZ=`cat /etc/timezone` -v digiskr:/opt/digiskr --tmpfs=/tmp/digiskr lazywalker/digiskr
```
You should see out just like:
```log
Timezone is Asia/Shanghai
2020-08-14 09:44:47,077 WARNING     1 [main] No tasks in queue.
2020-08-14 09:44:47,077 WARNING     1 [main] I'm out
```

Edit `/var/lib/docker/volumes/digiskr/_data/settings.py`, follow the `Configuration` section below, then run it again, if everything well you should see:
```log
2020-08-14 01:49:15,124 INFO      1 [main] current schedule is: {'szsdr': ['20!']}
2020-08-14 01:49:15,125 INFO      1 [main] QueueWorker QW-0 started
2020-08-14 01:49:15,126 INFO      1 [main] QueueWorker QW-1 started
2020-08-14 01:49:15,127 INFO      1 [main] QueueWorker QW-2 started
2020-08-14 01:49:15,127 INFO      1 [main] Started sound recorder szsdr-20!, timestamp=1597369756
```
You are good to go.

FYI, [Here](https://www.raspberrypi.org/blog/docker-comes-to-raspberry-pi/) is a quick setup guide for Raspberry Pi, for short, all you need to do is run `curl -sSL https://get.docker.com | sh`

TIPS: DO NOT use over 8 simultaneous tasks when you using docker on raspberry pi, it may cause memory leak to your kiwi.

# Docker Compose
If you prefer using a Docker Compose file, here's a basic example:
```
version: "3.7"
services:
  digiskimmer:
    container_name: digiskimmer
    image: lazywalker/digiskr
    restart: unless-stopped
    environment:
      # Set your preferred timezone
      TZ: America/Chicago
    volumes:
      - digiskr:/opt/digiskr

networks:
  digiskr:
volumes:
  digiskr:
    name: digiskr
```

# Manual Setup
If you want to do it manually follow those steps.
## 1. Preparation
To do so, first you need to install WSJT-X, the client that most people use for decoding FT8.

I use the jt9/wsprd command-line program within the WSJT-X to decode signals, then upload to http://pskreporter.info and http://wsprnet.org when work with wspr.

### For OSX

Download & Install WSJT-X from http://physics.princeton.edu/pulsar/k1jt/wsjtx-2.2.2-Darwin.dmg, open a terminal, then

```bash
sudo ln -s /Applications/wsjtx.app/Contents/MacOS/jt9 /usr/local/bin/jt9
sudo ln -s /Applications/wsjtx.app/Contents/MacOS/wsprd /usr/local/bin/wsprd
```

### For Raspberry pi
[follow this instructions](https://github.com/lazywalker/DigiSkimmer/wiki/Manual-Installation-on-RaspberryPi)

### For Debian
I only tested debian 11 - bullseye/sid, cause only this version have a ready-to-go wsjtx-2.2.2 package.
```bash
sudo apt update
sudo apt install wsjtx
```

DigiSkimmer is write in python3, make sure python3 is your default python interpreter, then you shoud install numpy and requests libraries
```bash
pip install requests numpy
```

Pull the code 
```bash
cd ~
git clone https://github.com/lazywalker/DigiSkimmer.git
cd DigiSkimmer
```

## 2. Configuration
You should modify `settings.py`

```bash
cp settings.py.template settings.py
```
if you upgrade from below v0.20.5, please do remember to copy your settings from the old config.py into settings.py, filename changed, sorry.

`STATIONS` is what kiwistation for, `SCHEDULES` is for the station/band hop, available bands are:
```
FT8: 10 12 15 17 20 30 40 60 80 160
FT4: 10 12 15 17 20 30 40 80
WSPR:10 12 15 17 20 30 40 80 160 630 2190
```

Configure your stations

```python
STATIONS = {
    'szsdr': {                                      ## name of kiwisdr station
        'server_host': 'szsdr.ddns.net',            ## url of your kiwisdr station
        'server_port': 8073,                        ## port of kiwi
        'password': 'passwor0d',                    ## password if needed
        'tlimit_password': 'passwor0d',             ## password to bypass time limited, if needed
        'callsign': 'BD7MQB',                       ## your callsign
        'grid': 'OL72an',                           ## your grid/locator, if none set will use the kiwisdr's setting
        #'antenna' : 'Longwire/Mini-whip'           ## if none set, it'll read the antenna information from the kiwisdr
    },
    
    ...
    # more stations goes here
}

SCHEDULES = {
    '21:00-08:00': {'czsdr': [20, 30, 40, 60, 80, 160]},
    '08:00-14:30': {'czsdr': [10, 12, 15, 17, 20, 30]},
    '14:30-21:00': {'czsdr': [10, 15, 17, 20, 30, 40]},

    ...
}

```

`UPDATE:` digiskr support `band hop`, you can use a specific slot(or more) to rotate between bands, this feature is very helpful when you don't have enough slots. 

* Use `|` to enable band hop, see the config below, 4 slots will be used, the last one is rotate between 60-80-160, one per minute.
* You can also specific what mode to spot, `~` for FT8(by default), `+` for FT4, `!` for WSPR.
* When using `'` or `|`, always remember to quote the band by `'`

```python
SCHEDULES = {

    # four slots all FT8, the last one is rotate between 60-80-160 when localtime is 21:00-08:00
    '21:00-08:00': {'szsdr': [20, 30, '40~', '60|80|160']},    

    # when localtime is 08:00-12:00
    '08:00-12:00': {
        # station no.1, slot1 is rotate between 20(FT8)-20(FT4), slot3 is 40(FT8)-40(FT4)
        'szsdr': ['20|20+', 30, '40~|40+', '60|80|160'],

        # station no.2, slot1 is rotate between 10-12-15-17-20-30-40 at FT8 mode, then 20-30-40 at FT4 mode
        'czsdr': ['10|12|15|17|20|30|40|20+|30+|40+'],

        # station no.3, slot1-4 working 10m/20m/30m/40m with WSPR mode at the same time, 
        # slot5 rotate from 20m to 40m with FT mode.
        'cdsdr': ['10!', '20!', '30!', '40!', '20+|30+|40m'],
    }
    ...
}

```


## 3. Start spotting
```bash
./fetch.py
```

BTW i use tmux to keep `fetch.py` running when console closed.

## 4. Track your spots
- Type your callsign into http://pskreporter.info and click the `find` button, enjoy. 
- For WSPR, you may also use http://wsprnet.org/drupal/wsprnet/spotquery .

---
This is free software, licensed under the GNU GENERAL PUBLIC LICENSE, Version 2.0, part of pskreporter/wsjt codes took from @jketterl/openwebrx, TNX

73 de BD7MQB, Michael
