# DigiSkimmer - FT8 skimmer base on kiwirecorder/KiwiSDR
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
git pull https://github.com/lazywalker/DigiSkimmer.git
cd DigiSkimmer
```

## 2. Configuration
You should modify `config.py`
```bash
STATIONS = {
    'szsdr': {                                      ## name of kiwisdr station
        'server_host': 'szsdr.ddns.net',            ## url of your kiwisdr station
        'server_port': 8073,                        ## port of kiwi
        'password': 'passwor0d',                    ## password if needed
        'tlimit_password': 'passwor0d',             ## password to bypass time limited, if needed
        'callsign': 'BD7MQB',                       ## your callsign
        'grid': 'OL72an',                           ## your grid
    },
    
    ...
}

SCHEDULES = {
    '21:00-08:00': {'czsdr': [20, 30, 40, 60, 80, 160]},
    '08:00-14:30': {'czsdr': [10, 12, 15, 17, 20, 30]},
    '14:30-21:00': {'czsdr': [10, 15, 17, 20, 30, 40]},

    ...
}


```


## 3. Start your journey of spotting
```bash
./ft8.py
```

BTW i use tmux to keep `ft8.py` running when console closed.

## 4. Track your spots
Type your callsign into http://pskreporter.info and click the `find` button, enjoy.


---
73 de BD7MQB, Michael