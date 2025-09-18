import os
import time
import logging
import yaml
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# --- MODIFICATION STARTS HERE ---
import zipfile
import shutil
# --- MODIFICATION ENDS HERE ---


# ----------------- Logging Setup -----------------
def setup_logging(log_file):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


# ----------------- Driver Factory -----------------
def create_driver(download_dir: str) -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/125.0.0.0 Safari/537.36")

    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    options.add_experimental_option("prefs", prefs)

    return webdriver.Chrome(options=options)


# ----------------- Downloader Class -----------------
class AnnualReportDownloader:
    # --- MODIFICATION: Updated constructor to accept unzipped path ---
    def __init__(self, symbol: str, base_download_dir: str, base_unzip_dir: str):
        self.symbol = symbol
        self.download_dir = os.path.join(os.path.abspath(base_download_dir), f"{symbol}/downloads")
        # --- MODIFICATION: Define the unzip directory ---
        self.unzip_dir = os.path.join(os.path.abspath(base_unzip_dir), self.symbol)
        
        os.makedirs(self.download_dir, exist_ok=True)
        # --- MODIFICATION: Create the unzip directory ---
        os.makedirs(self.unzip_dir, exist_ok=True)
        
        self.driver = create_driver(self.download_dir)
        self.wait = WebDriverWait(self.driver, 20)

    def open_company_page(self):
        url = f"https://www.nseindia.com/get-quotes/equity?symbol={self.symbol}"
        logging.info(f"Opening {url}")
        self.driver.get(url)

    def open_annual_reports_tab(self):
        try:
            annual_tab = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(text(),'Annual Reports')]"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", annual_tab)
            time.sleep(1)
            try:
                annual_tab.click()
            except ElementClickInterceptedException:
                logging.warning("Normal click failed, retrying with JS click...")
                self.driver.execute_script("arguments[0].click();", annual_tab)

            logging.info("Clicked on Annual Reports tab")
        except TimeoutException:
            logging.error("Annual Reports tab not found!")
            return False
        return True

    def download_reports(self):
        time.sleep(5)  # wait for page to load
        report_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf') or contains(@href, '.zip')]")

        if not report_links:
            logging.error(f"No report links found for {self.symbol}")
            return

        for idx, link in enumerate(report_links, start=1):
            href = link.get_attribute("href")
            year_text = link.text.strip() or f"Report_{idx}"

            year = next((part for part in year_text.split() if part.isdigit() and len(part) == 4), "UNKNOWN")
            ext = ".pdf" if ".pdf" in href.lower() else ".zip"
            file_name = f"ANNUAL_{year}{ext}"
            file_path = os.path.join(self.download_dir, file_name)

            logging.info(f"Triggering download for {year_text} -> {file_name}")
            try:
                # Use JS click for reliability
                self.driver.execute_script("arguments[0].click();", link)
                # Wait for download to start and potentially complete
                time.sleep(10) 
            except Exception as e:
                logging.error(f"Failed to click {year_text}: {e}")

        logging.info(f"Report downloads triggered. Waiting a bit more for them to complete...")
        time.sleep(15) # Extra wait for larger files to finish downloading
        logging.info(f"Downloads for {self.symbol} finished. Original files are in {self.download_dir}")

    # --- MODIFICATION STARTS HERE: New method to unzip and organize files ---
    def _unzip_and_organize_reports(self):
        """
        Unzips .zip files and copies other files from the download directory
        to the unzipped directory, leaving the original downloads intact.
        """
        logging.info(f"Organizing and unzipping files for {self.symbol} into: {self.unzip_dir}")
        
        try:
            downloaded_files = os.listdir(self.download_dir)
            if not downloaded_files:
                logging.warning(f"No files found in download directory for {self.symbol} to organize.")
                return

            for filename in downloaded_files:
                source_path = os.path.join(self.download_dir, filename)
                
                # If the item is a file
                if os.path.isfile(source_path):
                    # If it's a zip file, extract its contents
                    if filename.lower().endswith('.zip'):
                        try:
                            with zipfile.ZipFile(source_path, 'r') as zip_ref:
                                zip_ref.extractall(self.unzip_dir)
                            logging.info(f"Successfully unzipped '{filename}'")
                        except zipfile.BadZipFile:
                            logging.error(f"Error: '{filename}' is not a valid zip file or is corrupted.")
                        except Exception as e:
                            logging.error(f"Failed to unzip '{filename}': {e}")
                    # Otherwise, just copy the file
                    else:
                        try:
                            destination_path = os.path.join(self.unzip_dir, filename)
                            shutil.copy2(source_path, destination_path) # copy2 preserves metadata
                            logging.info(f"Copied '{filename}'")
                        except Exception as e:
                            logging.error(f"Failed to copy '{filename}': {e}")

        except Exception as e:
            logging.error(f"An error occurred during file organization for {self.symbol}: {e}")
    # --- MODIFICATION ENDS HERE ---

    def run(self):
        try:
            self.open_company_page()
            if self.open_annual_reports_tab():
                self.download_reports()
        finally:
            # --- MODIFICATION: Call the new organizer method before quitting ---
            self._unzip_and_organize_reports()
            self.driver.quit()
            logging.info(f"All reports processed for {self.symbol} [OK]")


# ----------------- Runner -----------------
if __name__ == "__main__":
    
    with open("downloader/config/downloader.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    csv_file = config["path"]["csv"]
    download_path = config["path"]["downloads"]
    log_path = config["path"]["logs"]
    # --- MODIFICATION STARTS HERE: Get unzipped path from config ---
    unzipped_path = config["path"]["unzipped"]
    # --- MODIFICATION ENDS HERE ---

    # Get the directory part of the log file path
    log_dir = os.path.dirname(log_path)
    # Create the log directory if it doesn't already exist
    os.makedirs(log_dir, exist_ok=True)

    setup_logging(log_path)

    tickers = pd.read_csv(csv_file)["ticker"].dropna().unique().tolist()

    logging.info(f"Found {len(tickers)} tickers in {csv_file}")

    for ticker in tickers:
        logging.info(f"Processing ticker: {ticker}")
        try:
            # --- MODIFICATION: Pass unzipped_path to the constructor ---
            downloader = AnnualReportDownloader(ticker, download_path, unzipped_path)
            downloader.run()
        except Exception as e:
            logging.error(f"A critical error occurred while processing {ticker}: {e}", exc_info=True)