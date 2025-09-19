Annual Report Downloader
This tool downloads and organizes annual reports for specified stock tickers from the NSE India website.

Project Structure
main.py: The main entry point for the application. Handles command-line arguments.

requirements.txt: A list of required Python packages.

config/: Contains the configuration files.

downloader.yaml: Defines paths for logs, downloads, etc.

data/: Contains the input CSV file with tickers.

downloader/: Module for handling all web scraping and downloading tasks.

driver.py: Configures and creates the Selenium WebDriver.

downloader.py: Contains the AnnualReportDownloader class.

organizer/: Module for processing downloaded files (unzipping, copying).

organizer.py: Contains the file organization logic.

utils/: A package for shared utility functions.

config.py: Loads the configuration file.

logging_setup.py: Configures the application's logger.

Setup
Create a virtual environment (recommended):

python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

Install the required packages:

pip install -r requirements.txt

How to Run
The tool is run from the command line via main.py.

1. Process a Single Ticker (Download & Unzip)

python main.py --ticker INFY

2. Process All Tickers from the Default CSV File
(Uses the CSV path specified in config/downloader.yaml)

python main.py

3. Process Tickers from a Specific CSV File

python main.py --csv-file path/to/your/tickers.csv

4. Download Only (No Unzipping)

python main.py --ticker RELIANCE --download-only

5. Unzip Only (For Already Downloaded Files)

python main.py --unzip-only
