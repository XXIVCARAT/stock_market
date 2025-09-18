import os
import time
import logging
import shutil
import zipfile
import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ----------------- Logging -----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ----------------- Load Config -----------------
def load_config():
    config_path = os.path.join(os.getcwd(), "config", "unzipper.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

# ----------------- Processor -----------------
def process_file(src_path, unzipped_dir):
    """Extract or copy file into unzipped_dir (overwrite mode)."""
    if not os.path.exists(src_path):
        return

    try:
        if src_path.lower().endswith(".zip"):
            with zipfile.ZipFile(src_path, "r") as zf:
                namelist = zf.namelist()

                if len(namelist) == 1:  # single file inside zip
                    target_path = os.path.join(unzipped_dir, os.path.basename(namelist[0]))
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(namelist[0]) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                    logging.info(f"Extracted single file {namelist[0]} -> {target_path}")

                else:  # multiple files
                    zip_name = os.path.splitext(os.path.basename(src_path))[0]
                    target_dir = os.path.join(unzipped_dir, zip_name)
                    os.makedirs(target_dir, exist_ok=True)

                    # overwrite existing files
                    for member in zf.namelist():
                        zf.extract(member, target_dir)
                    logging.info(f"Extracted multiple files from {src_path} -> {target_dir}")

        else:  # non-zip, copy as-is (overwrite if exists)
            target_path = os.path.join(unzipped_dir, os.path.basename(src_path))
            if os.path.isdir(src_path):
                shutil.copytree(src_path, target_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, target_path)
            logging.info(f"Copied {src_path} -> {target_path}")

    except Exception as e:
        logging.error(f"Failed to process {src_path}: {e}")

# ----------------- Event Handlers -----------------
class DownloadsHandler(FileSystemEventHandler):
    """Handles new or updated files in ticker downloads/ folder"""
    def __init__(self, unzipped_dir):
        self.unzipped_dir = unzipped_dir

    def _wait_for_file(self, filepath, timeout=30, interval=1):
        """Wait until file is stable (size not changing)."""
        start_time = time.time()
        last_size = -1

        while time.time() - start_time < timeout:
            try:
                size = os.path.getsize(filepath)
                if size == last_size:
                    return True
                last_size = size
            except FileNotFoundError:
                pass
            time.sleep(interval)
        return False

    def on_created(self, event):
        if not event.is_directory:
            logging.info(f"New file detected: {event.src_path}")
            if self._wait_for_file(event.src_path):
                process_file(event.src_path, self.unzipped_dir)
            else:
                logging.warning(f"File {event.src_path} not stable after timeout, skipping.")

    def on_modified(self, event):
        if not event.is_directory:
            logging.info(f"File updated: {event.src_path}")
            if self._wait_for_file(event.src_path):
                process_file(event.src_path, self.unzipped_dir)
            else:
                logging.warning(f"File {event.src_path} not stable after timeout, skipping.")

class ReportsHandler(FileSystemEventHandler):
    """Detects new ticker folders inside reports/"""
    def __init__(self, observers, reports_dir):
        self.observers = observers
        self.reports_dir = reports_dir

    def on_created(self, event):
        if event.is_directory:
            ticker_name = os.path.basename(event.src_path)
            logging.info(f"New ticker folder detected: {ticker_name}")
            watch_ticker(event.src_path, self.observers)

# ----------------- Watcher Functions -----------------
def watch_ticker(ticker_dir, observers):
    """Start watching a single ticker folder's downloads"""
    downloads_dir = os.path.join(ticker_dir, "downloads")
    unzipped_dir = os.path.join(ticker_dir, "unzipped")

    os.makedirs(downloads_dir, exist_ok=True)
    os.makedirs(unzipped_dir, exist_ok=True)

    # Process existing files first
    for item in os.listdir(downloads_dir):
        path = os.path.join(downloads_dir, item)
        process_file(path, unzipped_dir)

    # Start watcher
    event_handler = DownloadsHandler(unzipped_dir)
    observer = Observer()
    observer.schedule(event_handler, downloads_dir, recursive=False)
    observer.start()
    observers.append(observer)

    logging.info(f"Watching folder: {downloads_dir}")

def watch_and_process():
    config = load_config()
    reports_dir = config.get("reports_dir", "./reports")

    observers = []

    # Watch all existing ticker folders at startup
    for ticker in os.listdir(reports_dir):
        ticker_dir = os.path.join(reports_dir, ticker)
        if os.path.isdir(ticker_dir):
            watch_ticker(ticker_dir, observers)

    # Watch for new ticker folders dynamically
    reports_handler = ReportsHandler(observers, reports_dir)
    reports_observer = Observer()
    reports_observer.schedule(reports_handler, reports_dir, recursive=False)
    reports_observer.start()
    observers.append(reports_observer)

    logging.info(f"Watching root reports folder for new tickers: {reports_dir}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for obs in observers:
            obs.stop()
    for obs in observers:
        obs.join()

# ----------------- Run -----------------
if __name__ == "__main__":
    watch_and_process()
