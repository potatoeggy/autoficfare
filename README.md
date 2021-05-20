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

## Plugins

Other Python code can be run once stories are updated. All plugins must follow the sample `plugin.py` and be placed in the `plugins` folder. Plugins are given access to the configuration file in the form of a `ConfigParser` object, and the function `post_add_hook` is called with a list of tuples consisting of old and new metadata as dictionaries. See the [Calibre documentation for Metadata.all_non_none_fields()](https://manual.calibre-ebook.com/generated/en/template_ref.html#api-of-the-metadata-objects) for more information.