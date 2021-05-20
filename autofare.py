#!/usr/bin/python
from fanficfare import geturls
from fanficfare import cli
import json
import tempfile
import sys
import os
from contextlib import redirect_stdout
import io
import argparse
import configparser

try:
    import init_calibre
except ImportError:
    pass # if running via calibre-debug or not Linux

from calibre.library import db

FF_ARGS = [
    "--update-epub",
    "--progressbar",
    "--non-interactive"
    ]

arg_parser = argparse.ArgumentParser(description="Check if any stories have updated through IMAP and FanFicFare and add any found to Calibre")
# TODO: add later

# read configuration
config = configparser.ConfigParser()
config.read("config.ini")
try:
    conf = config["Configuration"]
    verbose = conf.getboolean("Verbose", fallback=False)
    calibre_path = conf.get("LibraryPath")
except KeyError:
    print("ERROR: Invalid general configuration.")

try:
    imap = config["IMAP"]
    imap_server = imap.get("Server", fallback="imap.gmail.com")
    imap_email = imap.get("Email")
    imap_password = imap.get("Password")
    imap_folder = imap.get("Folder")
    imap_mark_read = imap.getboolean("MarkUpdatesAsRead", fallback=True)
except KeyError:
    print("ERROR: Invalid IMAP configuration.")

class Log:
    def _log(self, msg, priority="DEBUG"):
        print(f"{priority}: {msg}")

    def debug(self, msg):
        if verbose:
            self._log(msg, "DEBUG")
    
    def info(self, msg):
        self._log(msg, "INFO")
    
    def warn(self, msg):
        self._log(msg, "WARN")
    
    def error(self, msg):
        self._log(msg, "ERROR")
    
log = Log()

def download_story(epub_path):
    output = io.StringIO()
    with redirect_stdout(output):
        cli.main(argv=FF_ARGS + [epub_path])
    output = output.getvalue()
    if "chapters, more than source:" in output:
        log.warn("More chapters found in local version.")
    elif "already contains" in output:
        log.info("No new chapters found - update may not yet have processed through site. Queuing for retry on next run.")
        # TODO: actually queue
    elif "No story url found in epub to update" in output:
        log.warn("No URL in EPUB to update from.")
    else:
        return True
    return False

tempdir = tempfile.gettempdir()
os.chdir(tempdir)
log.debug(f"Using temporary directory: {tempdir}")
db = db(calibre_path).new_api

log.info("Searching email for updated stories...")
story_urls = []
try:
    story_urls = geturls.get_urls_from_imap(imap_server, imap_email, imap_password, imap_folder, imap_mark_read)
except Exception:
    log.error("There was an error searching email. Please check your config.")

if len(story_urls) == 0:
    log.info("No story updates found.")

for i, s in enumerate(story_urls):
    log.info(f"Searching for {s} in Calibre database ({i+1}/{len(story_urls)})")
    calibre_id = int(next(iter(db.search(f"Identifiers:url:{s}")), -1))
    if calibre_id == -1:
        log.warn("Story not found in database. Skipping...")
        continue

    try:
        log.info("Story found in database. Exporting book...")
        db.copy_format_to(calibre_id, "epub", os.path.join(tempdir, "temp.epub")) # yikes hardcoded
    except Exception: # hopefully NoSuchFormat
        log.warn("Failed to export book. Skipping...")
        continue

    log.info("Export successful. Checking story for updates, this may take a while...")
    if not download_story(os.path.join(tempdir, "temp.epub")):
        log.info("Failed to update story or no updates found. Skipping...")
        continue
    
    log.info("Adding updated story to Calibre...")
    db.add_format(calibre_id, "epub", os.path.join(tempdir, "temp.epub"))
    log.info("Update for story {s} complete.")
