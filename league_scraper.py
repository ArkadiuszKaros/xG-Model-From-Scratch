import logging
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import pandas as pd
from numpy import random
import time
import os

logging.basicConfig(level = logging.INFO, format = "%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class League:
    def __init__(self, league, season, selenium_timeout = 8):
        self.league = league
        self.season = season
        self.selenium_timeout = selenium_timeout
        self.url = f'https://understat.com/league/{league}/{season}'
        self.driver = None
        self.scripts = None

    def __enter__(self):

        chrome_options = Options()
        chrome_options.add_argument("headless")
        chrome_options.add_argument("--log-level=3")
        self.driver = webdriver.Chrome(options = chrome_options)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if self.driver:
            self.driver.quit()

    def fetch_scripts(self, retries = 3, delay = 10):
        """
            Fetch scripts from the webpage and store them for reuse.
        """
        attempt = 0

        while attempt < retries and self.scripts is None:

            try:
                logger.info(f"Fetching scripts from {self.url} (Attempt {attempt + 1}/{retries})...")
                self.driver.get(self.url)
                WebDriverWait(self.driver, timeout = self.selenium_timeout)
                soup = BeautifulSoup(self.driver.page_source, features = "lxml")
                self.scripts = [script.string for script in soup.find_all('script') if script.string]

                break

            except Exception as e:

                logger.error(f"Error fetching scripts on attempt {attempt + 1}: {e}")
                
                attempt += 1

                if attempt < retries:
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error("Max retries reached. Failed to fetch scripts.")
                    raise

    def extract_data(self, keyword):
        """
        Extract data matching the given keyword from fetched scripts.
        """
        if self.scripts is None:
            raise ValueError("Scripts not fetched. Call fetch_scripts() before extracting data.")
        try:
            script = next(script for script in self.scripts if keyword in script)
            ind_start = script.index("('") + 2
            ind_stop = script.index("')")
            data = script[ind_start:ind_stop]
            data = data.encode("utf8").decode("unicode escape")
            
            return json.loads(data)
        
        except StopIteration:
            raise ValueError(f"No script found containing the keyword '{keyword}'.")
        except Exception as e:
            raise ValueError(f"Error extracting data for keyword '{keyword}': {e}")

    def get_data(self):
        """
            Fetch and save `matches`, `teams`, and `players` data in one go.
        """
        try:
            logger.info("Starting data download...")
            self.fetch_scripts()  # Fetch scripts once
            
            # Process matches

            matches = self.extract_data("datesData")
            matches_df = pd.json_normalize(matches, sep = "_")
            matches_df["league"] = self.league
            matches_df["season"] = self.season
            self.save_to_csv(matches_df, "matches")
            logger.info("Matches data fetched and saved.")
            
            # Process teams

            teams = self.extract_data("teamsData")
            teams_to_df = [
                pd.json_normalize(teams[team], "history", ["id", "title"], sep = "_")
                for team in teams.keys()
            ]
            teams_df = pd.concat(teams_to_df)
            teams_df["league"] = self.league
            teams_df["season"] = self.season
            self.save_to_csv(teams_df, "teams")
            logger.info("Teams data fetched and saved.")

            # Process players

            players = self.extract_data("playersData")
            players_df = pd.DataFrame(players)
            players_df["league"] = self.league
            players_df["season"] = self.season
            self.save_to_csv(players_df, "players")
            logger.info("Players data fetched and saved.")
            
            logger.info("Data fetching and saving completed successfully.")
        except Exception as e:
            logger.error(f"An error occurred during data fetching or saving: {e}")

    def save_to_csv(self, data, file_name, base_folder = "data"):

        """
            Save data to a CSV file in the specified folder.
        """
        os.makedirs(base_folder, exist_ok = True)

        filepath = os.path.join(base_folder, f"{file_name}_{self.league}_{self.season}.csv")
        data.to_csv(filepath, index = False, encoding = "utf-8")
        logger.info(f"File {file_name} saved to: {filepath}")

# with League("EPL", "2023") as league_season:
#     league_season.get_data()
