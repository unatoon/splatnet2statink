#!/usr/bin/env python
# -*- coding: utf-8 -*-

# eli fessler
# clovervidia
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from builtins import input
from builtins import zip
from builtins import str
from builtins import range
from past.utils import old_div
import os.path
import argparse
import sys
import requests
import json
import time
import datetime
import random
import re
import uuid
from io import BytesIO
from operator import itemgetter

from packaging import version
from subprocess import call

import iksm
import dbs
import salmonrun


A_VERSION = "1.7.1"


# place config.txt in same directory as script (bundled or not)
if getattr(sys, "frozen", False):
    app_path = os.path.dirname(sys.executable)
elif __file__:
    app_path = os.path.dirname(__file__)

config_path = os.path.join(app_path, "config.txt")

try:
    config_file = open(config_path, "r")
    config_data = json.load(config_file)
    config_file.close()
except (IOError, ValueError):
    print("Generating new config file.", file=sys.stderr)
    config_data = {"cookie": "", "user_lang": "", "session_token": ""}
    config_file = open(config_path, "w")
    config_file.seek(0)
    config_file.write(
        json.dumps(config_data, indent=4, sort_keys=True, separators=(",", ": "))
    )
    config_file.close()
    config_file = open(config_path, "r")
    config_data = json.load(config_file)
    config_file.close()

#########################
## API KEYS AND TOKENS ##
YOUR_COOKIE = config_data["cookie"]  # iksm_session
try:  # support for pre-v1.0.0 config.txts
    SESSION_TOKEN = config_data[
        "session_token"
    ]  # to generate new cookies in the future
except:
    SESSION_TOKEN = ""
USER_LANG = config_data[
    "user_lang"
]  # only works with your game region's supported languages
#########################

# print out payload and exit. can use with geargrabber2.py & saving battle jsons
debug = False

if "app_timezone_offset" in config_data:
    app_timezone_offset = str(config_data["app_timezone_offset"])
else:
    app_timezone_offset = str(
        int((time.mktime(time.gmtime()) - time.mktime(time.localtime())) / 60)
    )

if "app_unique_id" in config_data:
    app_unique_id = str(config_data["app_unique_id"])
else:
    app_unique_id = (
        "32449507786579989234"  # random 19-20 digit token. used for splatnet store
    )

if "app_user_agent" in config_data:
    app_user_agent = str(config_data["app_user_agent"])
else:
    app_user_agent = "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Mobile Safari/537.36"

app_head = {
    "Host": "app.splatoon2.nintendo.net",
    "x-unique-id": app_unique_id,
    "x-requested-with": "XMLHttpRequest",
    "x-timezone-offset": app_timezone_offset,
    "User-Agent": app_user_agent,
    "Accept": "*/*",
    "Referer": "https://app.splatoon2.nintendo.net/home",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": USER_LANG,
}

translate_weapons = dbs.weapons
translate_stages = dbs.stages
translate_profile_color = dbs.profile_colors
translate_fest_rank = dbs.fest_ranks
translate_headgear = dbs.headgears
translate_clothing = dbs.clothes
translate_shoes = dbs.shoes
translate_ability = dbs.abilities


def custom_key_exists(key, checkiftrue=False):
    """Checks if a given custom key exists in config.txt and, optionally, if it is set to true."""

    # https://github.com/frozenpandaman/splatnet2statink/wiki/custom-keys
    if key not in [
        "ignore_private",
        "app_timezone_offset",
        "app_unique_id",
        "app_user_agent",
    ]:
        print("(!) checking unexpected custom key")
    if checkiftrue:
        return (
            True if key in config_data and config_data[key].lower() == "true" else False
        )
    else:
        return True if key in config_data else False


def gen_new_cookie(reason):
    """Attempts to generate a new cookie in case the provided one is invalid."""

    manual = False

    if reason == "blank":
        print("Blank cookie.")
    elif reason == "auth":  # authentication error
        print("The stored cookie has expired.")
    else:  # server error or player hasn't battled before
        print(
            "Cannot access SplatNet 2 without having played at least one battle online."
        )
        sys.exit(1)
    if SESSION_TOKEN == "":
        print(
            "session_token is blank. Please log in to your Nintendo Account to obtain your session_token."
        )
        new_token = iksm.log_in(A_VERSION)
        if new_token == None:
            print("There was a problem logging you in. Please try again later.")
        else:
            if new_token == "skip":  # user has opted to manually enter cookie
                manual = True
                print(
                    "\nYou have opted against automatic cookie generation and must manually input your iksm_session cookie.\n"
                )
            else:
                print("\nWrote session_token to config.txt.")
            config_data["session_token"] = new_token
            write_config(config_data)
    elif SESSION_TOKEN == "skip":
        manual = True
        print(
            '\nYou have opted against automatic cookie generation and must manually input your iksm_session cookie. You may clear this setting by removing "skip" from the session_token field in config.txt.\n'
        )

    if manual:
        new_cookie = iksm.enter_cookie()
    else:
        print("Attempting to generate new cookie...")
        acc_name, new_cookie = iksm.get_cookie(SESSION_TOKEN, USER_LANG, A_VERSION)
    config_data["cookie"] = new_cookie
    write_config(config_data)
    if manual:
        print("Wrote iksm_session cookie to config.txt.")
    else:
        print("Wrote iksm_session cookie for {} to config.txt.".format(acc_name))


def write_config(tokens):
    """Writes config file and updates the global variables."""

    config_file = open(config_path, "w")
    config_file.seek(0)
    config_file.write(
        json.dumps(tokens, indent=4, sort_keys=True, separators=(",", ": "))
    )
    config_file.close()

    config_file = open(config_path, "r")
    config_data = json.load(config_file)

    global SESSION_TOKEN
    SESSION_TOKEN = config_data["session_token"]
    global YOUR_COOKIE
    YOUR_COOKIE = config_data["cookie"]
    global USER_LANG
    USER_LANG = config_data["user_lang"]

    config_file.close()


def load_json():
    """Returns results JSON from online."""

    url = "https://app.splatoon2.nintendo.net/api/results"
    results_list = requests.get(
        url, headers=app_head, cookies=dict(iksm_session=YOUR_COOKIE)
    )
    return json.loads(results_list.text)


def set_language():
    """Prompts the user to set their game language."""

    if USER_LANG == "":
        print("Default locale is ja-JP. Press Enter to accept, or enter your own (see readme for list).")
        language_code = input("")

        if language_code == "":
            config_data["user_lang"] = "ja-JP"
            write_config(config_data)
            return
        else:
            language_list = [
                "en-US",
                "es-MX",
                "fr-CA",
                "ja-JP",
                "en-GB",
                "es-ES",
                "fr-FR",
                "de-DE",
                "it-IT",
                "nl-NL",
                "ru-RU",
            ]
            while language_code not in language_list:
                print("Invalid language code. Please try entering it again.")
                language_code = input("")
            config_data["user_lang"] = language_code
            write_config(config_data)


def check_for_updates():
    """Checks the version of the script against
    the latest version in the repo and updates dbs.py."""

    if version is None:
        print("\n!! Unable to check for updates due to a new dependency in v1.6.0.")
        print(
            "!! Please re-run `pip install -r requirements.txt` (see readme for details). \n"
        )
    try:
        latest_script = requests.get(
            "https://raw.githubusercontent.com/frozenpandaman/splatnet2statink/master/splatnet2statink.py"
        )
        new_version = re.search(r'= "([\d.]*)"', latest_script.text).group(1)
        update_available = version.parse(new_version) != version.parse(A_VERSION)
        if update_available:
            print(
                "\nThere is a new version (v{}) available.".format(new_version), end=""
            )
            if os.path.isdir(".git"):  # git user
                update_now = input("\nWould you like to update now? [Y/n] ")
                if update_now == "" or update_now[0].lower() == "y":
                    FNULL = open(os.devnull, "w")
                    call(["git", "checkout", "."], stdout=FNULL, stderr=FNULL)
                    call(["git", "checkout", "master"], stdout=FNULL, stderr=FNULL)
                    call(["git", "pull"], stdout=FNULL, stderr=FNULL)
                    print(
                        "Successfully updated to v{}. Please restart splatnet2statink.".format(
                            new_version
                        )
                    )
                    return True
                else:
                    print(
                        "Remember to update later with `git pull` to get the latest version.\n"
                    )
            else:  # non-git user
                print(
                    " Visit the site below to update:\nhttps://github.com/frozenpandaman/splatnet2statink\n"
                )
                # dbs_freshness = time.time() - os.path.getmtime("dbs.py")
                if getattr(sys, "frozen", False):  # bundled
                    pass
                else:
                    latest_db = requests.get(
                        "https://raw.githubusercontent.com/frozenpandaman/splatnet2statink/master/dbs.py"
                    )
                    try:
                        if (
                            latest_db.status_code == 200
                        ):  # require proper response from github
                            local_db = open("dbs.py", "w")
                            local_db.write(latest_db.text)
                            local_db.close()
                    except:  # if we can't open the file
                        pass  # then we don't modify the database
    except:  # if there's a problem connecting to github - or can't access 'version' if 'packaging' not installed
        pass  # then we assume there's no update available


def main():
    """I/O and setup."""

    if check_for_updates():
        sys.exit(0)

    set_language()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-M",
        dest="N",
        required=False,
        nargs="?",
        action="store",
        help="monitoring mode; pull data every N secs (default: 300)",
        const=300,
    )
    parser.add_argument(
        "--salmon",
        required=False,
        action="store_true",
        help="uploads salmon run shifts",
    )
    parser.add_argument("-i", dest="filename", required=False, help=argparse.SUPPRESS)

    parser_result = parser.parse_args()

    filename = parser_result.filename
    salmon = parser_result.salmon

    salmon_and_not_r = (
        True if salmon and len(sys.argv) == 3 and "-r" not in sys.argv else False
    )
    salmon_and_more = True if salmon and len(sys.argv) > 3 else False
    if salmon_and_not_r or salmon_and_more:
        print("Can only use --salmon flag alone or with -r. Exiting.")
        sys.exit(1)

    if parser_result.N != None:
        try:
            m_value = int(parser_result.N)
        except ValueError:
            print("Number provided must be an integer. Exiting.")
            sys.exit(1)
        if m_value < 0:
            print("No.")
            sys.exit(1)
        elif m_value < 60:
            print("Minimum number of seconds in monitoring mode is 60. Exiting.")
            sys.exit(1)
    else:
        m_value = -1

    return m_value, filename, salmon


def get_battles():
    """Returns number of battles to upload along with results JSON."""

    while True:
        if filename != None:
            if not os.path.exists(filename):
                argparse.ArgumentParser().error(
                    "File {} does not exist!".format(filename)
                )  # exit
            with open(filename) as data_file:
                try:
                    data = json.load(data_file)
                except ValueError:
                    print("Could not decode JSON object in this file.")
                    sys.exit(1)
        else:  # no argument
            data = load_json()
        try:
            results = data["results"]
        except KeyError:  # either auth error json (online) or battle json (local file)
            if (
                filename != None
            ):  # local file given, so seems like battle instead of results json
                data = json.loads('{{"results": [{}]}}'.format(json.dumps(data)))
                try:
                    results = data["results"]
                except KeyError:
                    print("Ill-formatted JSON file.")
                    sys.exit(1)
            else:
                if YOUR_COOKIE == "":
                    reason = "blank"
                elif data["code"] == "AUTHENTICATION_ERROR":
                    reason = "auth"
                else:
                    reason = "other"
                gen_new_cookie(reason)
                continue

        return results


def get_battle(battle_number):
    url = "https://app.splatoon2.nintendo.net/api/results/{}".format(battle_number)
    battle = requests.get(
        url, headers=app_head, cookies=dict(iksm_session=YOUR_COOKIE)
    )
    return json.loads(battle.text)


def set_scoreboard(payload, battle_number, mystats, s_flag, battle_payload=None):
    """Returns a new payload with the players key (scoreboard) present."""

    if battle_payload != None:
        battledata = battle_payload
    else:
        url = "https://app.splatoon2.nintendo.net/api/results/{}".format(battle_number)
        battle = requests.get(
            url, headers=app_head, cookies=dict(iksm_session=YOUR_COOKIE)
        )
        print(battle.text)
        battledata = json.loads(battle.text)

    try:
        battledata["my_team_members"]  # only present in battle jsons
    except KeyError:
        print("Problem retrieving battle. Continuing without scoreboard statistics.")
        return payload  # same payload as passed in, no modifications

    # common definitions from the mystats payload
    mode = mystats[0]
    rule = mystats[1]
    result = mystats[2]
    k_or_a = mystats[3]
    death = mystats[4]
    special = mystats[5]
    weapon = mystats[6]
    level_before = mystats[7]
    rank_before = mystats[8]
    turfinked = mystats[9]
    try:
        title_before = translate_fest_rank[mystats[10]]
    except:
        pass
    principal_id = mystats[11]
    star_rank = mystats[12]
    gender = mystats[13]
    my_species = mystats[14]

    ally_scoreboard = []
    for n in range(len(battledata["my_team_members"])):
        ally_stats = []
        ally_stats.append(battledata["my_team_members"][n]["sort_score"])  # 0
        ally_stats.append(
            battledata["my_team_members"][n]["kill_count"]
            + battledata["my_team_members"][n]["assist_count"]
        )  # 1
        ally_stats.append(battledata["my_team_members"][n]["kill_count"])  # 2
        ally_stats.append(battledata["my_team_members"][n]["special_count"])  # 3
        ally_stats.append(battledata["my_team_members"][n]["death_count"])  # 4
        ally_stats.append(
            "#{}".format(battledata["my_team_members"][n]["player"]["weapon"]["id"])
        )  # 5
        ally_stats.append(
            battledata["my_team_members"][n]["player"]["player_rank"]
        )  # 6
        if mode == "gachi" or mode == "league":
            try:
                ally_stats.append(
                    battledata["my_team_members"][n]["player"]["udemae"]["name"].lower()
                )  # 7
            except:
                ally_stats.append(None)  # 7
            ally_stats.append(battledata["my_team_members"][n]["game_paint_point"])  # 8
        elif mode == "regular" or mode == "fes":
            ally_stats.append(None)  # 7 - udemae (rank) is null in turf war
            if result == "victory":
                ally_stats.append(
                    battledata["my_team_members"][n]["game_paint_point"] + 1000
                )  # 8
            else:
                ally_stats.append(
                    battledata["my_team_members"][n]["game_paint_point"]
                )  # 8
        ally_stats.append(1)  # 9 - my team? (yes)
        ally_stats.append(0)  # 10 - is me? (no)
        if s_flag:
            ally_stats.append(None)  # 11
        else:
            ally_stats.append(
                battledata["my_team_members"][n]["player"]["nickname"]
            )  # 11
        if mode == "fes":
            ally_stats.append(
                translate_fest_rank[
                    battledata["my_team_members"][n]["player"]["fes_grade"]["rank"]
                ]
            )  # 12
        else:
            ally_stats.append(None)  # 12
        ally_pid = battledata["my_team_members"][n]["player"]["principal_id"]
        if s_flag:
            ally_stats.append(None)  # 13
        else:
            ally_stats.append(ally_pid)  # 13
        ally_stats.append(battledata["my_team_members"][n]["player"]["star_rank"])  # 14
        ally_stats.append(
            battledata["my_team_members"][n]["player"]["player_type"]["style"]
        )  # 15
        ally_stats.append(
            battledata["my_team_members"][n]["player"]["player_type"]["species"][:-1]
        )  # 16
        try:
            if (
                battledata["crown_players"] != None
                and ally_pid in battledata["crown_players"]
            ):
                ally_stats.append("yes")  # 17
            else:
                ally_stats.append("no")  # 17
        except:
            ally_stats.append("no")  # 17
        ally_scoreboard.append(ally_stats)

    my_stats = []
    my_stats.append(battledata["player_result"]["sort_score"])  # 0
    my_stats.append(k_or_a)  # 1
    my_stats.append(battledata["player_result"]["kill_count"])  # 2
    my_stats.append(special)  # 3
    my_stats.append(death)  # 4
    my_stats.append("#{}".format(weapon))  # 5
    my_stats.append(level_before)  # 6
    if mode == "gachi" or mode == "league":
        my_stats.append(rank_before)  # 7
        my_stats.append(turfinked)  # 8
    elif mode == "regular" or mode == "fes":
        my_stats.append(None)  # 7 - udemae (rank) is null in turf war
        if result == "victory":
            my_stats.append(turfinked + 1000)  # 8
        else:
            my_stats.append(turfinked)  # 8
    my_stats.append(1)  # 9 - my team? (yes)
    my_stats.append(1)  # 10 - is me? (yes)
    my_stats.append(battledata["player_result"]["player"]["nickname"])  # 11
    if mode == "fes":
        my_stats.append(title_before)  # 12
    else:
        my_stats.append(None)  # 12
    my_stats.append(principal_id)  # 13
    my_stats.append(star_rank)  # 14
    my_stats.append(gender)  # 15
    my_stats.append(my_species)  # 16
    try:
        if (
            battledata["crown_players"] != None
            and principal_id in battledata["crown_players"]
        ):
            my_stats.append("yes")  # 17
        else:
            my_stats.append("no")  # 17
    except:
        my_stats.append("no")  # 17
    ally_scoreboard.append(my_stats)

    # scoreboard sort order: sort_score (or turf inked), k+a, specials, deaths (more = better), kills, nickname
    # discussion: https://github.com/frozenpandaman/splatnet2statink/issues/6
    if rule != "turf_war":
        if s_flag:
            sorted_ally_scoreboard = sorted(
                ally_scoreboard, key=itemgetter(0, 1, 3, 4, 2), reverse=True
            )
        else:
            sorted_ally_scoreboard = sorted(
                ally_scoreboard, key=itemgetter(0, 1, 3, 4, 2, 11), reverse=True
            )
    else:
        if s_flag:
            sorted_ally_scoreboard = sorted(
                ally_scoreboard, key=itemgetter(8, 1, 3, 4, 2), reverse=True
            )
        else:
            sorted_ally_scoreboard = sorted(
                ally_scoreboard, key=itemgetter(8, 1, 3, 4, 2, 11), reverse=True
            )

    for n in range(len(sorted_ally_scoreboard)):
        if (
            sorted_ally_scoreboard[n][10] == 1
        ):  # if it's me, position in sorted list is my rank in team
            payload["rank_in_team"] = n + 1  # account for 0 indexing
            break

    enemy_scoreboard = []
    for n in range(len(battledata["other_team_members"])):
        enemy_stats = []
        enemy_stats.append(battledata["other_team_members"][n]["sort_score"])  # 0
        enemy_stats.append(
            battledata["other_team_members"][n]["kill_count"]
            + battledata["other_team_members"][n]["assist_count"]
        )  # 1
        enemy_stats.append(battledata["other_team_members"][n]["kill_count"])  # 2
        enemy_stats.append(battledata["other_team_members"][n]["special_count"])  # 3
        enemy_stats.append(battledata["other_team_members"][n]["death_count"])  # 4
        enemy_stats.append(
            "#{}".format(battledata["other_team_members"][n]["player"]["weapon"]["id"])
        )  # 5
        enemy_stats.append(
            battledata["other_team_members"][n]["player"]["player_rank"]
        )  # 6
        if mode == "gachi" or mode == "league":
            try:
                enemy_stats.append(
                    battledata["other_team_members"][n]["player"]["udemae"][
                        "name"
                    ].lower()
                )  # 7
            except:
                enemy_stats.append(None)  # 7
            enemy_stats.append(
                battledata["other_team_members"][n]["game_paint_point"]
            )  # 8
        elif mode == "regular" or mode == "fes":
            enemy_stats.append(None)  # 7 - udemae (rank) is null in turf war
            if result == "defeat":
                enemy_stats.append(
                    battledata["other_team_members"][n]["game_paint_point"] + 1000
                )  # 8
            else:
                enemy_stats.append(
                    battledata["other_team_members"][n]["game_paint_point"]
                )  # 8
        enemy_stats.append(0)  # 9 - my team? (no)
        enemy_stats.append(0)  # 10 - is me? (no)
        if s_flag:
            enemy_stats.append(None)  # 11
        else:
            enemy_stats.append(
                battledata["other_team_members"][n]["player"]["nickname"]
            )  # 11
        if mode == "fes":
            enemy_stats.append(
                translate_fest_rank[
                    battledata["other_team_members"][n]["player"]["fes_grade"]["rank"]
                ]
            )  # 12
        else:
            enemy_stats.append(None)  # 12
        enemy_pid = battledata["other_team_members"][n]["player"]["principal_id"]
        if s_flag:
            enemy_stats.append(None)  # 13
        else:
            enemy_stats.append(enemy_pid)  # 13
        enemy_stats.append(
            battledata["other_team_members"][n]["player"]["star_rank"]
        )  # 14
        enemy_stats.append(
            battledata["other_team_members"][n]["player"]["player_type"]["style"]
        )  # 15
        enemy_stats.append(
            battledata["other_team_members"][n]["player"]["player_type"]["species"][:-1]
        )  # 16
        try:
            if (
                battledata["crown_players"] != None
                and enemy_pid in battledata["crown_players"]
            ):
                enemy_stats.append("yes")  # 17
            else:
                enemy_stats.append("no")  # 17
        except:
            enemy_stats.append("no")  # 17
        enemy_scoreboard.append(enemy_stats)

    if rule != "turf_war":
        sorted_enemy_scoreboard = sorted(
            enemy_scoreboard, key=itemgetter(0, 1, 3, 4, 2, 11), reverse=True
        )
    else:
        sorted_enemy_scoreboard = sorted(
            enemy_scoreboard, key=itemgetter(8, 1, 3, 4, 2, 11), reverse=True
        )

    full_scoreboard = sorted_ally_scoreboard + sorted_enemy_scoreboard

    payload["players"] = []
    for n in range(len(full_scoreboard)):
        # sort score, k+a, kills, specials, deaths, weapon, level, rank, turf inked, is my team, is me, nickname, splatfest rank, splatnet principal_id, star_rank, gender, species, top_500
        detail = {
            "team": "my" if full_scoreboard[n][9] == 1 else "his",
            "is_me": "yes" if full_scoreboard[n][10] == 1 else "no",
            "weapon": full_scoreboard[n][5],
            "level": full_scoreboard[n][6],
            "rank_in_team": n + 1
            if n < 4
            else n - 3,  # pos 0-7 on scoreboard -> 1-4 for each
            "kill_or_assist": full_scoreboard[n][1],
            "kill": full_scoreboard[n][2],
            "death": full_scoreboard[n][4],
            "special": full_scoreboard[n][3],
            "point": full_scoreboard[n][8],
            "name": full_scoreboard[n][11],
            "splatnet_id": full_scoreboard[n][13],
            "star_rank": full_scoreboard[n][14],
            "gender": full_scoreboard[n][15],
            "species": full_scoreboard[n][16],
        }
        try:
            detail["top_500"] = full_scoreboard[n][17]
        except:
            pass
        if mode == "gachi" or mode == "league":
            detail["rank"] = full_scoreboard[n][7]
        if mode == "fes":
            detail["fest_title"] = full_scoreboard[n][12]
        payload["players"].append(detail)

    if s_flag:
        for i in range(len(battledata["my_team_members"])):
            battledata["my_team_members"][i]["player"]["nickname"] = None
            battledata["my_team_members"][i]["player"]["principal_id"] = None
        for i in range(len(battledata["other_team_members"])):
            battledata["other_team_members"][i]["player"]["nickname"] = None
            battledata["other_team_members"][i]["player"]["principal_id"] = None

    if not debug:  # we should already have our original json if we're using debug mode
        payload["splatnet_json"] = battledata

    return payload  # return modified payload w/ players key


if __name__ == "__main__":
    m_value, filename, salmon = main()
    if salmon:  # salmon run mode
        salmonrun.upload_salmon_run(A_VERSION, YOUR_COOKIE, API_KEY, app_head, is_r)
    else:  # normal mode
        results = get_battles()
        battles = [get_battle(result['battle_number']) for result in results]
        print(json.dumps(battles, ensure_ascii=False))
