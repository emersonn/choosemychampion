from colorama import Fore
import sqlalchemy, datetime, requests, math

# todo: make this into a package instead
from models import Match, Champion, BannedChampion, BuiltItems, ChampionData
from database import db_session
from settings import API_KEY, URLS

# takes all the champion data of Champions and Matches and summarizes it into
# ChampionData models which is summary data of particular champions (and their
# roles). outputs the data into a dataframe which is displayed as a table
# in console
def analyze_db_to_excel():
    import pandas as pd
    all_matches = Match.query.all()
    all_champions = Champion.query.all()

    print("Analyzing database. There are: " + Fore.GREEN + str(len(all_matches)) +
        Fore.RESET + " matches in record.")

    champion_names = {}
    champion_data = {}

    for champion in all_champions:
        try:
            champion_name = champion_names[champion.champion_id]
        except KeyError:
            print("Making request to get champion name...")
            r = requests.get(URLS['champion'] + str(champion.champion_id), params = {'api_key': API_KEY})
            champion_names[champion.champion_id] = r.json()['name']
            champion_name = champion_names[champion.champion_id]

        # need to differentiate champions that fill multiple roles
        try:
            champ = champion_data[champion_name]
        except KeyError:
            champion_data[champion_name] = {'won': 0,
                'seen': 0, 'kills': 0, 'deaths': 0, 'assists': 0, 'damage': 0,
                'objective_score': 0, 'tower_score': 0}
            champ = champion_data[champion_name]

        if champion.won:
            champ['won'] += 1
        champ['seen'] += 1
        champ['kills'] += champion.kills
        champ['deaths'] += champion.deaths
        champ['assists'] += champion.assists
        champ['damage'] += champion.damage
        champ['objective_score'] += champion.objective_score
        champ['tower_score'] += champion.tower_score

    for champion in champion_data:
        data = champion_data[champion]

        data['won'] = data['won'] * 1.0 / data['seen']
        data['kills'] = data['kills'] * 1.0 / data['seen']
        data['deaths'] = data['deaths'] * 1.0 / data['seen']
        data['assists'] = data['assists'] * 1.0 / data['seen']
        data['damage'] = data['damage'] * 1.0 / data['seen']
        data['objective_score'] = data['objective_score'] * 1.0 / data['seen']
        data['tower_score'] = data['tower_score'] * 1.0 / data['seen']
        data['pick_rate'] = data['seen'] * 1.0 / len(all_matches)

    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    # data_frame = pd.DataFrame(champion_data).T
    data_frame = pd.DataFrame.from_dict(champion_data, orient='index')
    print(data_frame)

    data_frame.to_excel('database/Analyzed.xls')

# analyzes all champions and matches on file and summarizes it into ChampionData
# table which allows for analysis of data without having to go through all records
def analyze_db():
    # queries all the champion and match data
    all_matches = Match.query.all()
    all_champions = Champion.query.all()

    print("Analyzing database. There are: " + Fore.GREEN + str(len(all_matches)) +
        Fore.RESET + " matches in record.")

    champion_data = {}

    # attempts to iterate through all the champions
    for champion in all_champions:
        print("Analyzing champion: " + Fore.GREEN + str(champion.champion_id) + Fore.RESET + ".")
        try:
            # tries requesting the particular champion if it exists within
            # the dictionary
            champ = champion_data[(champion.champion_id, champion.role)]
        except KeyError:
            # if the champion does not exist in the dictionary it creates
            # a new key, value pair to work with
            champion_data[(champion.champion_id, champion.role)] = {'won': 0,
                'seen': 0, 'kills': 0, 'deaths': 0, 'assists': 0, 'damage': 0,
                'objective_score': 0, 'tower_score': 0}
            champ = champion_data[(champion.champion_id, champion.role)]

        # assigns all values into the dictionary
        if champion.won:
            champ['won'] += 1
        champ['seen'] += 1
        champ['kills'] += champion.kills
        champ['deaths'] += champion.deaths
        champ['assists'] += champion.assists
        champ['damage'] += champion.damage
        champ['objective_score'] += champion.objective_score
        champ['tower_score'] += champion.tower_score

    # iterates through the champion dictionary and begins to
    # average everything by the seen values to the 5th decimal place
    # todo: optimize this, clean this up
    for champion in champion_data:
        data = champion_data[champion]

        data['won'] = round(data['won'] * 1.0 / data['seen'], 5)
        data['kills'] = round(data['kills'] * 1.0 / data['seen'], 5)
        data['deaths'] = round(data['deaths'] * 1.0 / data['seen'], 5)
        data['assists'] = round(data['assists'] * 1.0 / data['seen'], 5)
        data['damage'] = round(data['damage'] * 1.0 / data['seen'], 5)
        data['objective_score'] = round(data['objective_score'] * 1.0 / data['seen'], 5)
        data['tower_score'] = round(data['tower_score'] * 1.0 / data['seen'], 5)
        data['pick_rate'] = round(data['seen'] * 1.0 / len(all_matches), 5)

        data_id, data_role = champion
        query = ChampionData.query.filter(ChampionData.champion_id == data_id,
            ChampionData.role == data_role).first()

        # todo:
        # if the database hasn't been populated yet
        # maybe put this logic somewhere else? maybe put it in the database
        # creation step? when wiping the database or creating a new database?

        # checks if the ChampionData exists for this particular champion
        # if it doesn't exist it creates a new record, otherwise it updates the
        # current ChampionData record
        if query == None:
            query = ChampionData(champion_id = data_id, role = data_role,
                won = data['won'], num_seen = data['seen'], kills = data['kills'], deaths = data['deaths'],
                assists = data['assists'], damage = data['damage'], objective_score = data['objective_score'],
                tower_score = data['tower_score'], pick_rate = data['pick_rate'], adjustment = 0)
            db_session.add(query)
        else:
            query.won = data['won']
            query.num_seen = data['seen']
            query.kills = data['kills']
            query.deaths = data['deaths']
            query.assists = data['assists']
            query.damage = data['damage']
            query.objective_score = data['objective_score']
            query.tower_score = data['tower_score']
            query.pick_rate = data['pick_rate']

        db_session.commit()
    db_session.commit()        

if __name__ == '__main__':
    analyze_db()
