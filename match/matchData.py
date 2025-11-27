import csv
import os
import requests

# Leagues and seasons (adjust seasons as needed)
LEAGUES = {
    "en.1": {  # Premier League
        "name": "Premier League",
        "url_template": "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/en.1.json",
        "seasons": ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023_2024"]
    },
    "es.1": {  # La Liga
        "name": "La Liga",
        "url_template": "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/es.1.json",
        "seasons": ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023_2024"]
    },
    "it.1": {  # Serie A
        "name": "Serie A",
        "url_template": "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/it.1.json",
        "seasons": ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023_2024"]
    },
    "de.1": {  # Bundesliga
        "name": "Bundesliga",
        "url_template": "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/de.1.json",
        "seasons": ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023_2024"]
    },
    "fr.1": {  # Ligue 1
        "name": "Ligue 1",
        "url_template": "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/fr.1.json",
        "seasons": ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023_2024"]
    },
    "sa.1": {  # Saudi Pro League
        "name": "Saudi Pro League",
        "url_template": "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/sa.1.json",
        "seasons": ["2022-23"]  # Only recent seasons available
    },
    "us.1": {  # MLS
        "name": "MLS",
        "url_template": "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/us.1.json",
        "seasons": ["2018", "2019", "2020", "2021", "2022", "2023"]
    }
}

OUTPUT_DIR = "openfootball_csvs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def fetch_season_json(url):
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"⚠️ Failed to fetch {url} (status: {resp.status_code})")
        return None


def determine_result(home_score, away_score):
    """Home-centric result: win/loss/draw from home team perspective"""
    if home_score is None or away_score is None:
        return ""
    if home_score > away_score:
        return "win"
    elif home_score < away_score:
        return "loss"
    else:
        return "draw"


def season_to_csv(league_code, season, league_name, data):
    filename = os.path.join(OUTPUT_DIR, f"{league_code}_{season}.csv")
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["Date", "Home Team", "Away Team", "Home Score", "Away Score", "Result"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for match in data.get("matches", []):
            ft_score = match.get("score", {}).get("ft", [None, None])
            home_score, away_score = ft_score if ft_score else (None, None)

            writer.writerow({
                "Date": match.get("date"),
                "Home Team": match.get("team1"),
                "Away Team": match.get("team2"),
                "Home Score": home_score,
                "Away Score": away_score,
                "Result": determine_result(home_score, away_score)
            })
    print(f"✅ Saved {filename}")


def main():
    for league_code, league_data in LEAGUES.items():
        for season in league_data["seasons"]:
            url = league_data["url_template"].format(season=season)
            json_data = fetch_season_json(url)
            if json_data:
                season_to_csv(league_code, season, league_data["name"], json_data)


if __name__ == "__main__":
    main()