from django.db import models
from django.db.models import JSONField
from rest_framework import serializers

class HourlyPlayerCount(models.Model):
    timestamp_hour = models.DateTimeField()
    player_count = models.IntegerField()

    class Meta:
        db_table = 'hourly_player_count'
        ordering = ['timestamp_hour']

class DailyPlaytime(models.Model):
    serialnumber = models.BigIntegerField()
    leaderboard_name = models.CharField(max_length=255)
    playfabid = models.CharField(max_length=255)
    stat_value = models.BigIntegerField()

class PlaytimeEx(models.Model):
    serialnumber = models.BigIntegerField()
    leaderboard_name = models.CharField(max_length=255)
    playfabid = models.CharField(max_length=255)
    stat_value = models.BigIntegerField()

class LatestLeaderboard(models.Model):
    leaderboard_name = models.CharField(max_length=255, primary_key=True)
    serialnumber = models.IntegerField()
    
    class Meta:
        db_table = 'latest_leaderboards'

class Player(models.Model):
    playfabid = models.CharField(max_length=16, primary_key=True)
    alias_history = JSONField(default=dict)
    alias_recent = models.CharField(max_length=255, blank=True, null=True)
    badlist = models.BooleanField(default=False)
    badlist_reason = models.CharField(max_length=255, blank=True, null=True)
    badlist_timestamp = models.DateTimeField(blank=True, null=True)
    lastseen_serial = models.IntegerField()
    peasant_cap = models.BooleanField(default=False)
    peasant_cap_date = models.DateTimeField(null=True, blank=True)
    gd = models.IntegerField(default=0)  # Assuming 'gd' represents an integer value
    cr = models.IntegerField(default=0)  # Similarly for 'cr'
    
    def aliases(self):
        if self.alias_history:
            return list(self.alias_history.keys())
        else:
            return []

    def most_common_alias(self):
        if self.alias_history:
            return max(self.alias_history, key=self.alias_history.get)
        else:
            return None

    class Meta:
        db_table = 'players'

class Leaderboard(models.Model):
    playfabid = models.ForeignKey(Player, on_delete=models.DO_NOTHING, db_column='playfabid')  # Change is here
    stat_value = models.IntegerField()
    serialnumber = models.IntegerField()

    class Meta:
        abstract = True

class ChivstatsSumstats(models.Model):
    serial_date = models.BigIntegerField(primary_key=True)
    unique_players = models.IntegerField()
    daily_players = models.IntegerField()

    class Meta:
        db_table = 'chivstats_sumstats'

class MetaAverageDailyPlaytime(models.Model):
    serialnumber = models.IntegerField(primary_key=True)
    playfabid = models.ForeignKey(Player, on_delete=models.DO_NOTHING, db_column='playfabid')  # Change is here
    stat_value = models.IntegerField()

    class Meta:
        db_table = 'meta_averagedailyplaytime'


# Define class names and corresponding table names
# Define class names
leaderboard_classes = [
    "GlobalXp", "Playtime", "PlaytimeEx", "DailyPlaytime", "ExperienceArcher", "ExperienceFootman", "ExperienceVanguard", "ExperienceKnight", "ExperienceWeaponMorningStar", "ExperienceWeaponHeavyCavalrySword",
    "ExperienceWeaponThrowingMallet", "ExperienceWeaponDagger", "ExperienceWeaponMediumShield", "ExperienceWeaponHeavyShield", "ExperienceWeaponWarBow", "ExperienceWeaponShovel",
    "ExperienceWeaponQuarterstaff", "ExperienceWeaponRapier", "ExperienceWeaponWarHammer", "ExperienceWeaponThrowingAxe", "ExperienceWeaponExecutionersAxe", "ExperienceWeaponCrossbow",
    "ExperienceWeaponPoleHammer", "ExperienceWeaponAxe", "ExperienceWeaponHeavyMace", "ExperienceWeaponBow", "ExperienceWeaponKnife", "ExperienceWeaponPickAxe",
    "ExperienceWeaponCudgel", "ExperienceWeaponFalchion", "ExperienceWeaponWarClub", "ExperienceWeaponSpear", "ExperienceWeaponShortSword", "ExperienceWeaponOneHandedSpear",
    "ExperienceWeaponLance", "ExperienceWeaponBattleAxe", "ExperienceWeaponGlaive", "ExperienceWeaponMace", "ExperienceWeaponHalberd", "ExperienceWeaponHighlandSword",
    "ExperienceWeaponPoleAxe", "ExperienceWeaponKatars", "ExperienceWeaponMaul", "ExperienceWeaponDaneAxe", "ExperienceWeaponBastardSword", "ExperienceWeaponJavelin",
    "ExperienceWeaponGreatsword", "ExperienceWeaponSword", "ExperienceWeaponSledgeHammer", "ExperienceWeaponLightShield", "ExperienceWeaponTwoHandedHammer", "ExperienceWeaponHatchet",
    "ExperienceWeaponWarAxe", "ExperienceWeaponThrowingKnife", "ExperienceWeaponMesser", "ExperienceWeaponHeavyCrossbow"
]

model_classes = {}
#TODO:use one table and reorganize and/or take a deeper look at schema
for class_name in leaderboard_classes:
    table_name = class_name.lower()
    meta_class = type('Meta', (), {'db_table': table_name})
    new_class = type(class_name, (Leaderboard,), {'__module__': __name__, 'Meta': meta_class})
    globals()[class_name] = new_class
    
    # Dynamically create serializer for each class
    serializer_meta_class = type('Meta', (), {'model': new_class, 'fields': ['playfabid', 'stat_value', 'serialnumber']})
    serializer_class = type(f"{class_name}Serializer", (serializers.ModelSerializer,), {'Meta': serializer_meta_class})
    globals()[f"{class_name}Serializer"] = serializer_class

class RankedPlayer(models.Model):
    player_id = models.IntegerField(unique=True)
    elo_rating = models.BigIntegerField(default=1500)
    discord_username = models.CharField(max_length=255, blank=True)
    kills = models.IntegerField(default=0)
    deaths = models.IntegerField(default=0)
    common_name = models.CharField(max_length=255, blank=True)
    playfabid = models.CharField(max_length=255, blank=True)
    discordid = models.BigIntegerField(blank=True, null=True)
    matches = models.IntegerField(default=0)
    gamename = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'ranked_players'