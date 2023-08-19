import re


def humanize_leaderboard_name(leaderboard_name):
    return re.sub(r'(?<!^)([A-Z])', r' \1', leaderboard_name.replace('ExperienceWeapon', '')).title().lower()
