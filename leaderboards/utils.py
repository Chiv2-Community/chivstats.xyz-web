import json
import os
import re
from copy import copy
from datetime import date, datetime

import yaml

from .models import (leaderboard_classes)

NEWS_DIR = os.path.dirname(os.path.abspath(__file__))+"/news.yaml"

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def read_yaml_news():
    #returns python news object from yaml
    with open(NEWS_DIR, 'r') as file:
        news = yaml.safe_load(file)
    return news


def to_json(obj, prettyPrint=False):
    #print json from python object
    return json.dumps(obj, indent=None if prettyPrint==False else 4, default=json_serial)

WeaponCategoryIndicator='ExperienceWeapon'
def organize_sidebar(leaderboard_name):
    weaponized_name = leaderboard_name.replace(WeaponCategoryIndicator, '')
    if weaponized_name == leaderboard_name:
        return "0" + leaderboard_name
    else:
        return "1" + weaponized_name

def categorize_sidebar(leaderboard_name):
    if organize_sidebar(leaderboard_name).startswith("0"):
        return "experience"
    else:
        return "weapon"

def humanize_leaderboard_name(leaderboard_name):
    return re.sub(r'(?<!^)([A-Z])', r' \1', leaderboard_name.replace(WeaponCategoryIndicator, '')).title()

def create_leaderboard_list():
    leaderboard_list_of_dict = []
    leaderboard_list_of_dict.append(dict(url="", leaderboard='Experience', category="category"))
    currentCategory = 'experience'
    leaderboards = copy(leaderboard_classes);
    # For now simple alphabetical order
    leaderboards.sort(key=organize_sidebar);

    for leaderboardItem in leaderboards:
        if currentCategory != categorize_sidebar(leaderboardItem):
            leaderboard_list_of_dict.append(dict(url="", leaderboard='Weapons', category="category"))
            currentCategory = categorize_sidebar(leaderboardItem)
        leaderboard_list_of_dict.append(dict(url=leaderboardItem, leaderboard=humanize_leaderboard_name(leaderboardItem), category=categorize_sidebar(leaderboardItem)))
    return leaderboard_list_of_dict

