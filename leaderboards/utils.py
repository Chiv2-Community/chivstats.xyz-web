import re
from copy import copy

from .models import (leaderboard_classes)

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

