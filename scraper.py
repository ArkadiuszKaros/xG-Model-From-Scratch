import logging
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import pandas as pd
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class League:
    def __init__(self, league, season, selenium_timeout = 8):
        self.league = league
        self.season = season
        self.selenium_timeout = selenium_timeout
        self.url = f'https://understat.com/league/{league}/{season}'
        self.driver = None

    def __enter__(self):

        chrome_options = Options()
        chrome_options.add_argument('headless')
        self.driver = webdriver.Chrome(options = chrome_options)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):

        if self.driver:
            self.driver.quit()

    def get_scripts(self, retries = 3, delay = 10):

        attempt = 0

        while attempt < retries:
            try:
                logger.info(f"Fetching scripts from {self.url} (Attempt {attempt + 1}/{retries})...")
                
                self.driver.get(self.url)
                WebDriverWait(self.driver, timeout=self.selenium_timeout)

                soup = BeautifulSoup(self.driver.page_source, features = 'lxml')
                scripts = soup.find_all('script')

                return [script.string for script in scripts if script.string is not None]

            except Exception as e:
                logger.error(f"Error fetching scripts on attempt {attempt + 1}: {e}")

                attempt += 1

                if attempt < retries:
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error("Max retries reached. Returning empty list.")
                    return []

    def _extract_data(self, keyword):

        scripts = self.get_scripts()

        # Check if scripts is empty

        if not scripts:
            raise ValueError(f"Scripts list is empty. Failed to fetch data for keyword '{keyword}'.")
        
        try:
            script = next(script for script in scripts if keyword in script)
        except StopIteration:
                raise ValueError(f"No script found containing the keyword '{keyword}'.")

        ind_start = script.index("('") + 2
        ind_stop = script.index("')")

        data = script[ind_start:ind_stop]
        data = data.encode('utf8').decode('unicode escape')

        return json.loads(data)

    def get_matches(self):

        matches = self._extract_data('datesData')
        matches = pd.json_normalize(matches, sep = '_')
        matches['league'] = self.league
        matches['season'] = self.season

        return matches

    def get_teams(self):

        teams = self._extract_data('teamsData')

        teams_to_df = [
            pd.json_normalize(teams[team], 'history', ['id', 'title'], sep = '_')
            for team in teams.keys()
        ]

        teams_df = pd.concat(teams_to_df)
        teams_df['league'] = self.league
        teams_df['season'] = self.season

        return teams_df

    def get_players(self):

        players = self._extract_data('playersData')
        players_df = pd.DataFrame(players)
        players_df['league'] = self.league
        players_df['season'] = self.season

        return players_df
    
# with League('EPL', '2023') as league_season:
#     matches = league_season.get_matches()
#     teams = league_season.get_teams()
#     players = league_season.get_players()

#     matches.to_csv('matches.csv', index = False)
#     teams.to_csv('teams.csv', index = False)
#     players.to_csv('players.csv', index = False)
