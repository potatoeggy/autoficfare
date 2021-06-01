#!/usr/bin/python
from fanficfare import geturls
from fanficfare import cli
import tempfile
import os
from contextlib import redirect_stdout
import io
import sys
import configparser

try:
    import init_calibre
    from calibre.library import db
except ImportError:
    print("ERROR: No Calibre import available. Ensure that this script is being run with calibre-debug or that the init_calibre module is accessible.")
    exit()

FF_ARGS = [
    "--update-epub",
    "--non-interactive"
]
RETRY_FILE = "retry.txt"
PLUGIN_DIR = "plugins"

# read configuration
config = configparser.ConfigParser()
config.read("config.ini")
try:
    conf = config["autoficfare"]
    verbose = conf.getboolean("Verbose", fallback=False)
    calibre_path = conf.get("LibraryPath")
    add_new_stories = conf.getboolean("AddNewStories", fallback=False)
    suppress_output = conf.getboolean("Quiet", fallback=False)
except KeyError:
    print("ERROR: Invalid general configuration.")
    exit(1)

try:
    imap = config["imap"]
    imap_server = imap.get("Server", fallback="imap.gmail.com")
    imap_email = imap.get("Email")
    imap_password = imap.get("Password")
    imap_folder = imap.get("Folder")
    imap_mark_read = imap.getboolean("MarkUpdatesAsRead", fallback=True)
except KeyError:
    print("ERROR: Invalid IMAP configuration.")
    exit(1)

# log handler
class Log:
    def __init__(self, suppress_output: bool):
        self.suppress_output = suppress_output
    
    def _log(self, msg, priority="DEBUG"):
        if self.suppress_output:
            return
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


log = Log(suppress_output)

# load plugins
log.debug("Loading plugins")
plugins = {}
sys.path.insert(0, PLUGIN_DIR)
for f in os.listdir(PLUGIN_DIR):
    fname, ext = os.path.splitext(f)
    if ext == ".py":
        module = __import__(fname)
        try:
            plugins[fname] = module.Plugin(config)
            if not "post_add_hook" in dir(plugins[fname]):
                raise AttributeError
        except AttributeError:
            log.warn(f"{fname} is in the plugins directory but does not have a proper plugin structure.")
        log.debug(f"Loaded plugin {module}")
sys.path.pop(0)
log.info(f"Loaded {len(plugins)} plugin(s).")

def download_story(epub_path, retry_url):
    output = io.StringIO()
    # catch fanficfare's output and read to check if update was successful
    with redirect_stdout(output):
        cli.main(argv=FF_ARGS + [epub_path])
    output = output.getvalue()
    if "chapters, more than source:" in output:
        log.warn("More chapters found in local version.")
    elif "already contains" in output:
        log.info("No new chapters found - update may not yet have processed through site. Queuing for retry on next run.")
        with open(RETRY_FILE, "a") as file:
            file.write(retry_url + "\n")
    elif "No story url found in epub to update" in output:
        log.warn("No URL in EPUB to update from.")
    elif "version 2 challenge" in output:
        log.info("Encountered an unsolvable Cloudflare challenge. Queuing for retry on next run.")
        with open(RETRY_FILE, "a") as file:
            file.write(retry_url + "\n")
    else:
        return True
    return False


def clean_story_link(link):
    # works for FFNet and AO3
    strings = link.split("/")
    for i, s in enumerate(strings):
        if s.isnumeric():
            return "/".join(strings[:i+1])
    log.warn(f"{link} is not a parsable or valid story link, this may cause issues.")
    return link

# perform work in temporary directory
tempdir = tempfile.gettempdir()
log.debug(f"Using temporary directory: {tempdir}")
db = db(calibre_path).new_api

# import retry links
story_urls = []
if os.path.isfile(RETRY_FILE):
    log.info("Searching for previously failed updates...")
    with open(RETRY_FILE) as file:
        story_urls += file.read().splitlines()
    os.remove(RETRY_FILE)

log.info("Searching email for updated stories...")
try:
    story_urls += list(map(clean_story_link, geturls.get_urls_from_imap(
        imap_server, imap_email, imap_password, imap_folder, imap_mark_read)))
except Exception:
    log.error("There was an error searching email. Please check your config.")

log.info(f"Found {len(story_urls)} stories to update.")
successful_updates = 0
metadata_list = []
for i, s in enumerate(story_urls):
    log.info(f"Searching for {s} in Calibre database ({i+1}/{len(story_urls)})")
    calibre_id = int(next(iter(db.search(f"Identifiers:url:{s}")), -1))
    if calibre_id == -1:
        log.warn("Story not found in database. Skipping...")
        continue

    old_metadata = db.get_metadata(calibre_id).all_non_none_fields()
    try:
        log.debug(f"{old_metadata['title']} - {', '.join(old_metadata['authors'])} found in database. Exporting book...")
        epub_path = db.format(calibre_id, "epub", as_path=True)
        if epub_path is None:
            raise Exception("File copy failed.")
    except Exception:  # hopefully NoSuchFormat
        log.warn("Failed to export story. Skipping...")
        continue

    log.info(f"Successfully found and exported {old_metadata['title']} - {', '.join(old_metadata['authors'])}. Updating story, this may take a while...")
    if not download_story(epub_path, s):
        continue

    log.debug("Adding updated story to Calibre...")
    db.add_format(calibre_id, "epub", epub_path)
    new_metadata = db.get_metadata(calibre_id).all_non_none_fields()
    log.info(f"Update for story {new_metadata['title']} - {', '.join(new_metadata['authors'])} successful.")
    successful_updates += 1
    metadata_list.append((old_metadata, new_metadata))

if successful_updates > 0:
    # post-process hook
    for name, plugin in plugins.items():
        log.info(f"Running post-library hook for plugin {name}...")
        plugin.post_add_hook(metadata_list)

log.info(f"Finished. {successful_updates}/{len(story_urls)} story updates successful.")
