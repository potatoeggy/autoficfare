# autoficfare

A Python script to check if any fanfiction has updated from email alerts using [FanFicFare](https://github.com/JimmXinu/FanFicFare) and updates them in [Calibre](https://github.com/kovidgoyal/calibre).

## Prerequisites

 - Python >= 3.8
 - The FanFicFare Python module/CLI (can be installed using `pip`)
 - Calibre

## Running

If Calibre was installed from source, the script can be run directly.

```
$ python3 autoficfare.py
```

Otherwise, the script should be run in Calibre's debug environment.

```
$ calibre-debug autoficfare.py
```

## Configuration

Follow the example in the sample configuration.