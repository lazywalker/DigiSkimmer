# DigiSkimmer - FT8/FT4 skimmer base on kiwirecorder/KiwiSDR
The idea was learned from [wsprdaemon](https://raw.githubusercontent.com/rrobinett/wsprdaemon), yet FT8 mode is more and more popular nowdays, more signals, easer to pickup(compared to wspr, some people use maga watt to transmit FT8). 

This can be useful in determining propagation conditions or in adjusting antenna. A wide band antenna kiwisdr located in urban area in my case, with 10 bands requests at the same time, can be easily reach over 10,000 spots within 24 hours.

It is also interesting to see how long it takes to spot 100 different DXCC/countries. (A well placed station with a decent antenna can do this within a week of monitoring, but the best systems can do it within a single day).

## 1. Preparation
To do so, first you need to install WSJT-X, the client that most people use for decoding FT8.

I use the jt9 command-line program within the WSJT-X to decode signals, a perl script `pskr.pl` to upload all spottings to http://pskreporter.info .

### For OSX

Download & Install WSJT-X from http://physics.princeton.edu/pulsar/k1jt/wsjtx-2.2.2-Darwin.dmg, open a terminal, then

```bash
sudo ln -s /Applications/wsjtx.app/Contents/MacOS/jt9 /usr/local/bin/jt9
```

### For Raspberry pi
```bash
wget http://physics.princeton.edu/pulsar/k1jt/wsjtx_2.2.2_armhf.deb
sudo dpkg -i wsjtx_2.2.2_armhf.de
```

### For Debian (I only tested debian 11 - bullseye/si)
```bash
sudo apt update
sudo apt install wsjtx
```

DigiSkimmer is write in python, then you shoud install numpy
```bash
pip install numpy
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
`STATIONS` is what kiwistation for, `SCHEDULES` is for the station/band hop, avaliable bands are:
```
FT8: 10 12 15 17 20 30 40 60 80 160
FT4: 10 12 15 17 20 30 40 80
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
* You can also specifi what mode to spot, `~` for FT8(by default), `+` for FT4.
* When using `'` or `|`, always remember to quote the band by `'`

```python
SCHEDULES = {

    # four slots all FT8, the last one is rotate between 60-80-160 when localtime is 21:00-08:00
    '21:00-08:00': {'szsdr': [20, 30, '40~', '60|80|160']},    

    # when localtime is 08:00-12:00
    '08:00-12:00': {
        # station no.1, slot1 is rotate between 20(FT8)-20(FT4), slot3 is 40(FT8)-40(FT4)
        'szsdr': ['20|20+', 30, '40~|40+', '60|80|160'],

        # station no.2, slot1 is rotate between 10-12-15-17-20-30-40 at mode FT8, then 20-30-40 at mode FT4
        'czsdr': ['10|12|15|17|20|30|40|20+|30+|40+'],
    }
    ...
}

```


## 3. Start spotting
```bash
./fetch.py
```

BTW i use tmux to keep `ft8.py` running when console closed.

## 4. Track your spots
Type your callsign into http://pskreporter.info and click the `find` button, enjoy.


---
- This is free software, licensed under the GNU GENERAL PUBLIC LICENSE, Version 2.0
- Part of pskreporter/wsjt codes were taken from @jketterl/openwebrx, TNX

73 de BD7MQB, Michael