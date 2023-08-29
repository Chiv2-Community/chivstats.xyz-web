# serializers.py
from rest_framework import serializers
from .models import Leaderboard, LatestLeaderboard, Player, leaderboard_classes  # Import your leaderboard model
from .models import (
    GlobalXp, Playtime, DailyPlaytime, PlaytimeEx, ExperienceArcher,
    ExperienceFootman, ExperienceVanguard, ExperienceKnight,
    ExperienceWeaponMorningStar, ExperienceWeaponHeavyCavalrySword,
    ExperienceWeaponThrowingMallet, ExperienceWeaponDagger,
    ExperienceWeaponMediumShield, ExperienceWeaponHeavyShield,
    ExperienceWeaponWarBow, ExperienceWeaponShovel, ExperienceWeaponQuarterstaff,
    ExperienceWeaponRapier, ExperienceWeaponWarHammer, ExperienceWeaponThrowingAxe,
    ExperienceWeaponExecutionersAxe, ExperienceWeaponCrossbow,
    ExperienceWeaponPoleHammer, ExperienceWeaponAxe, ExperienceWeaponHeavyMace,
    ExperienceWeaponBow, ExperienceWeaponKnife, ExperienceWeaponPickAxe,
    ExperienceWeaponCudgel, ExperienceWeaponFalchion, ExperienceWeaponWarClub,
    ExperienceWeaponSpear, ExperienceWeaponShortSword, ExperienceWeaponOneHandedSpear,
    ExperienceWeaponLance, ExperienceWeaponBattleAxe, ExperienceWeaponGlaive,
    ExperienceWeaponMace, ExperienceWeaponHalberd, ExperienceWeaponHighlandSword,
    ExperienceWeaponPoleAxe, ExperienceWeaponKatars, ExperienceWeaponMaul,
    ExperienceWeaponDaneAxe, ExperienceWeaponBastardSword, ExperienceWeaponJavelin,
    ExperienceWeaponGreatsword, ExperienceWeaponSword, ExperienceWeaponSledgeHammer,
    ExperienceWeaponLightShield, ExperienceWeaponTwoHandedHammer, ExperienceWeaponHatchet,
    ExperienceWeaponWarAxe, ExperienceWeaponThrowingKnife, ExperienceWeaponMesser,
    ExperienceWeaponHeavyCrossbow
)

model_mapping = {
    'GlobalXp': GlobalXp,
    'Playtime': Playtime,
    'DailyPlaytime': DailyPlaytime,
    'PlaytimeEx': PlaytimeEx,
    'ExperienceArcher': ExperienceArcher,
    'ExperienceFootman': ExperienceFootman,
    'ExperienceVanguard': ExperienceVanguard,
    'ExperienceKnight': ExperienceKnight,
    'ExperienceWeaponMorningStar': ExperienceWeaponMorningStar,
    'ExperienceWeaponHeavyCavalrySword': ExperienceWeaponHeavyCavalrySword,
    'ExperienceWeaponThrowingMallet': ExperienceWeaponThrowingMallet,
    'ExperienceWeaponDagger': ExperienceWeaponDagger,
    'ExperienceWeaponMediumShield': ExperienceWeaponMediumShield,
    'ExperienceWeaponHeavyShield': ExperienceWeaponHeavyShield,
    'ExperienceWeaponWarBow': ExperienceWeaponWarBow,
    'ExperienceWeaponShovel': ExperienceWeaponShovel,
    'ExperienceWeaponQuarterstaff': ExperienceWeaponQuarterstaff,
    'ExperienceWeaponRapier': ExperienceWeaponRapier,
    'ExperienceWeaponWarHammer': ExperienceWeaponWarHammer,
    'ExperienceWeaponThrowingAxe': ExperienceWeaponThrowingAxe,
    'ExperienceWeaponExecutionersAxe': ExperienceWeaponExecutionersAxe,
    'ExperienceWeaponCrossbow': ExperienceWeaponCrossbow,
    'ExperienceWeaponPoleHammer': ExperienceWeaponPoleHammer,
    'ExperienceWeaponAxe': ExperienceWeaponAxe,
    'ExperienceWeaponHeavyMace': ExperienceWeaponHeavyMace,
    'ExperienceWeaponBow': ExperienceWeaponBow,
    'ExperienceWeaponKnife': ExperienceWeaponKnife,
    'ExperienceWeaponPickAxe': ExperienceWeaponPickAxe,
    'ExperienceWeaponCudgel': ExperienceWeaponCudgel,
    'ExperienceWeaponFalchion': ExperienceWeaponFalchion,
    'ExperienceWeaponWarClub': ExperienceWeaponWarClub,
    'ExperienceWeaponSpear': ExperienceWeaponSpear,
    'ExperienceWeaponShortSword': ExperienceWeaponShortSword,
    'ExperienceWeaponOneHandedSpear': ExperienceWeaponOneHandedSpear,
    'ExperienceWeaponLance': ExperienceWeaponLance,
    'ExperienceWeaponBattleAxe': ExperienceWeaponBattleAxe,
    'ExperienceWeaponGlaive': ExperienceWeaponGlaive,
    'ExperienceWeaponMace': ExperienceWeaponMace,
    'ExperienceWeaponHalberd': ExperienceWeaponHalberd,
    'ExperienceWeaponHighlandSword': ExperienceWeaponHighlandSword,
    'ExperienceWeaponPoleAxe': ExperienceWeaponPoleAxe,
    'ExperienceWeaponKatars': ExperienceWeaponKatars,
    'ExperienceWeaponMaul': ExperienceWeaponMaul,
    'ExperienceWeaponDaneAxe': ExperienceWeaponDaneAxe,
    'ExperienceWeaponBastardSword': ExperienceWeaponBastardSword,
    'ExperienceWeaponJavelin': ExperienceWeaponJavelin,
    'ExperienceWeaponGreatsword': ExperienceWeaponGreatsword,
    'ExperienceWeaponSword': ExperienceWeaponSword,
    'ExperienceWeaponSledgeHammer': ExperienceWeaponSledgeHammer,
    'ExperienceWeaponLightShield': ExperienceWeaponLightShield,
    'ExperienceWeaponTwoHandedHammer': ExperienceWeaponTwoHandedHammer,
    'ExperienceWeaponHatchet': ExperienceWeaponHatchet,
    'ExperienceWeaponWarAxe': ExperienceWeaponWarAxe,
    'ExperienceWeaponThrowingKnife': ExperienceWeaponThrowingKnife,
    'ExperienceWeaponMesser': ExperienceWeaponMesser,
    'ExperienceWeaponHeavyCrossbow': ExperienceWeaponHeavyCrossbow
}


class LeaderboardSerializer(serializers.ModelSerializer):
    most_common_alias = serializers.SerializerMethodField()

    class Meta:
        model = Leaderboard
        fields = ['playfabid', 'stat_value', 'serialnumber', 'most_common_alias']
    
    def get_most_common_alias(self, obj):
        # Assuming the related name for Player is 'player'
        player = obj.playfabid
        if player:
            return player.most_common_alias()
        return None

class LatestLeaderboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = LatestLeaderboard
        fields = '__all__' # or specify the fields you want to expose through the API

class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ['playfabid', 'most_common_alias']

# Dynamically create serializers for each leaderboard class
for class_name in leaderboard_classes:
    #print("Globals: ", globals())
    #print("Leaderboard Classes: ", leaderboard_classes)
    new_class = type(f'{class_name}Serializer', (serializers.ModelSerializer,), {
        'class Meta': type('Meta', (), {'model': model_mapping[class_name], 'fields': ['playfabid', 'stat_value', 'serialnumber']})
    })
    globals()[f'{class_name}Serializer'] = new_class