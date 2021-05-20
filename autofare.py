#!/usr/bin/python
from fanficfare import geturls
from fanficfare import cli
import json
import tempfile
import sys
import os
from contextlib import redirect_stdout
import io

try:
    import init_calibre
except ImportError:
    pass # if running via calibre-debug or not Linux

from calibre.library import db

VERBOSE = True
FF_ARGS = [
    "--update-epub",
    "--progressbar",
    "--non-interactive"
    ]
CALIBRE_PATH = "/media/Stories"
IMAP_EMAIL = ""
IMAP_PASSWORD = ""
IMAP_FOLDER = "FF"
IMAP_SERVER = "imap.gmail.com"
IMAP_MARK_READ = True

class Log:
    def _log(self, msg, priority="DEBUG"):
        print(f"{priority}: {msg}")

    def debug(self, msg):
        if VERBOSE:
            self._log(msg, "DEBUG")
    
    def info(self, msg):
        self._log(msg, "INFO")
    
    def warn(self, msg):
        self._log(msg, "WARN")
    
    def error(self, msg):
        self._log(msg, "ERROR")
    
log = Log()
tempdir = tempfile.gettempdir()
os.chdir(tempdir)
log.debug(f"Using temporary directory: {tempdir}")
db = db(CALIBRE_PATH).new_api

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

log.info("Searching email for updated stories...")
story_urls = []
try:
    story_urls = geturls.get_urls_from_imap(IMAP_SERVER, IMAP_EMAIL, IMAP_PASSWORD, IMAP_FOLDER, IMAP_MARK_READ)
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
