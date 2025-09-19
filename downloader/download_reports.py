import os
import time
import glob
import logging
import yaml
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException


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
    # Run in headless mode (no browser window)
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


# ----------------- Download Wait Helper -----------------
def wait_for_downloads(download_dir, timeout=120):
    """
    Wait until all downloads in download_dir are complete (no .crdownload files).
    """
    logging.info("Waiting for downloads to complete...")
    end_time = time.time() + timeout
    while time.time() < end_time:
        files = glob.glob(os.path.join(download_dir, "*"))
        if files and all(not f.endswith(".crdownload") for f in files):
            return True
        time.sleep(1)
    return False


# ----------------- Downloader Class -----------------
class AnnualReportDownloader:
    def __init__(self, symbol: str, base_download_dir: str):
        self.symbol = symbol
        self.download_dir = os.path.join(os.path.abspath(base_download_dir), f"{symbol}_D")
        os.makedirs(self.download_dir, exist_ok=True)
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
            link_text = link.text.strip() or f"Report_{idx}"

            logging.info(f"Triggering download for: {link_text}")
            try:
                # If href is a direct PDF/ZIP link -> use requests
                if href and href.lower().endswith((".pdf", ".zip")):
                    file_name = os.path.basename(href.split("?")[0])  # keep original filename
                    file_path = os.path.join(self.download_dir, file_name)

                    r = requests.get(href, stream=True, headers={"User-Agent": "Mozilla/5.0"})
                    with open(file_path, "wb") as f:
                        for chunk in r.iter_content(1024):
                            f.write(chunk)
                    logging.info(f"Downloaded directly: {file_name}")
                else:
                    # Otherwise click via Selenium
                    self.driver.execute_script("arguments[0].click();", link)
                    if wait_for_downloads(self.download_dir, timeout=120):
                        files = glob.glob(os.path.join(self.download_dir, "*"))
                        for f in files:
                            logging.info(f"Downloaded via browser: {os.path.basename(f)}")
                    else:
                        logging.warning(f"Download timeout: {link_text}")
            except Exception as e:
                logging.error(f"Failed to download {link_text}: {e}")

        logging.info(f"Reports downloaded to {self.download_dir}")

    def run(self):
        try:
            self.open_company_page()
            if self.open_annual_reports_tab():
                self.download_reports()
        finally:
            self.driver.quit()
            logging.info(f"All reports processed for {self.symbol} [OK]")


# ----------------- Runner -----------------
if __name__ == "__main__":

    with open("downloader/config/downloader.yaml", "r") as f:
        config = yaml.safe_load(f)

    csv_file = config["path"]["csv"]
    download_path = config["path"]["downloads"]
    log_path = config["path"]["logs"]

    # Ensure log directory exists
    log_dir = os.path.dirname(log_path)
    os.makedirs(log_dir, exist_ok=True)

    setup_logging(log_path)

    tickers = pd.read_csv(csv_file)["ticker"].dropna().unique().tolist()

    logging.info(f"Found {len(tickers)} tickers in {csv_file}")

    for ticker in tickers:
        logging.info(f"Processing ticker: {ticker}")
        try:
            downloader = AnnualReportDownloader(ticker, download_path)
            downloader.run()
        except Exception as e:
            logging.error(f"Error while processing {ticker}: {e}")
