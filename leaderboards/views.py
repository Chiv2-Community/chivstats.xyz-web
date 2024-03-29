import re, json
from copy import copy
from datetime import datetime, timedelta
from collections import defaultdict
from django.utils.dateformat import DateFormat
from django.apps import apps
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import connection
from django.db.models import Avg, Max, Sum, Q, F, Subquery, OuterRef
from django.http import Http404, JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_page

from django.db.models import Case, When, Value, FloatField, Window, F, ExpressionWrapper
from django.db.models.functions import Rank

from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from leaderboards import models
from .models import (
    Leaderboard, Player, PlaytimeEx, GlobalXp, HourlyPlayerCount, ChivstatsSumstats, DailyPlaytime, leaderboard_classes, LatestLeaderboard, RankedPlayer,
    DuoTeam, Duel)
from .serializers import (LatestLeaderboardSerializer, PlayerSerializer)
from .serializers import LeaderboardSerializer
from .utils import (humanize_leaderboard_name, organize_sidebar, create_leaderboard_list, read_yaml_news, to_json, get_level_data)

from geoip2.database import Reader
from geoip2.errors import AddressNotFoundError, GeoIP2Error

leaderboards = copy(leaderboard_classes);
leaderboards.sort(key=organize_sidebar);
leaderboard_list_of_dict = create_leaderboard_list()

def calculate_level_and_gold(xp):
    level_data = get_level_data()
    level = 0
    total_gold = 0
    for level_info in level_data:
        if xp >= level_info['xp']:
            level = level_info['level']
            total_gold += level_info['reward']
        else:
            break
    return level, total_gold

def xp_ratio_scatter(request):
    context = {
        'leaderboards': leaderboard_list_of_dict,
    }

    return render(request, 'leaderboards/xp_ratio_scatter.html', context)


def peasant_caps_leaderboard(request):
    players_with_caps = Player.objects.filter(peasant_cap=True).order_by('peasant_cap_date')
    
    # Add last_seen_formatted field
    for player in players_with_caps:
        if player.lastseen_serial:
            # Convert the serial number to a date string
            last_seen_formatted = datetime.strptime(str(player.lastseen_serial)[:8], '%Y%m%d').strftime('%Y-%m-%d')
            player.last_seen_formatted = last_seen_formatted
        else:
            player.last_seen_formatted = 'Never'

    context = {
        'players': players_with_caps,
        'leaderboards': leaderboard_list_of_dict,
    }
    return render(request, 'leaderboards/peasant_caps_leaderboard.html', context)

from django.core.paginator import Paginator


def about_elo(request):
    # Add any dynamic content to the context as needed, for now it's empty.
    context = {}
    return render(request, 'leaderboards/about_elo.html', context)

def wealth_leaderboard(request):
    wealth_type = request.GET.get('wealth_type', 'gold')  # Default to 'gold' if not specified
    page = request.GET.get('page', 1)

    if wealth_type == 'gold':
        players_query = Player.objects.all().order_by('-gd')
    else:  # Default to Crowns if wealth_type is not 'gold'
        players_query = Player.objects.all().order_by('-cr')

    paginator = Paginator(players_query, 50)  # Show 50 players per page
    players = paginator.get_page(page)

    start_index = players.start_index()  # Get the start index for the current page

    # Add 'wealth' and 'rank' attributes to each player object
    for index, player in enumerate(players, start=start_index):
        player.wealth = player.gd if wealth_type == 'gold' else player.cr
        player.rank = index

    context = {
        'players': players,
        'wealth_type': wealth_type,
        'leaderboards': leaderboard_list_of_dict,
    }
    return render(request, 'leaderboards/wealth_leaderboard.html', context)

def ranked_combat_leaderboard(request):
    page = request.GET.get('page', 1)
    ranked_players_list = RankedPlayer.objects.all().order_by('-elo_duelsx')  # Updated field name here
    
    # Debugging: Check if the query set returns any results
    print('Ranked Players List:', ranked_players_list)

    paginator = Paginator(ranked_players_list, 50)  # Adjust the number per page as needed
    ranked_players_page = paginator.get_page(page)

    playfabids = [ranked_player.playfabid for ranked_player in ranked_players_page]
    players = Player.objects.filter(playfabid__in=playfabids).in_bulk(field_name='playfabid')

    players_data = []
    for ranked_player in ranked_players_page:
        # Get the related Player object from the pre-fetched players dictionary
        player = players.get(ranked_player.playfabid)
        
        # Determine the display name using the order of precedence you've given
        display_name = ranked_player.gamename or ranked_player.common_name or (player.most_common_alias() if player else None)
        
        # Round the elo_duelsx value to the nearest whole number
        elo_rating_rounded = round(ranked_player.elo_duelsx)
        
        # Append the player data with the chosen display name and the rounded ELO rating
        players_data.append({
            'playfabid': ranked_player.playfabid,
            'common_name': display_name,
            'elo_rating': elo_rating_rounded,  # Use the rounded value here
            'matches': ranked_player.matches,
            'kills': ranked_player.kills,
            'deaths': ranked_player.deaths
        })

    # New code for fetching and processing DuoTeam data
    duo_teams_list = DuoTeam.objects.filter(retired=False).order_by('-elo_rating')  # Adjust the filter and order as needed
    duo_paginator = Paginator(duo_teams_list, 10)  # Adjust the number per page as needed
    page_duo = request.GET.get('page_duo', 1)
    duo_teams_page = duo_paginator.get_page(page_duo)

    duo_teams_data = []
    for team in duo_teams_page:
        try:
            player1 = RankedPlayer.objects.get(playfabid=team.player1_id)
            player2 = RankedPlayer.objects.get(playfabid=team.player2_id)
            team_data = {
                'team_name': team.team_name or f"{player1.common_name} & {player2.common_name}",
                'elo_rating': team.elo_rating,
                'matches_played': team.matches_played,
                'player1_name': player1.common_name,
                'player2_name': player2.common_name
            }
            duo_teams_data.append(team_data)
        except RankedPlayer.DoesNotExist:
            # Handle the case where one of the players does not exist
            # For example, skip this team or add a placeholder
            continue


    context = {
        'duo_teams_data': duo_teams_data,
        'duo_teams_page': duo_teams_page,
        'players_data': players_data,  # Make sure this matches the template variable
        'ranked_players_page': ranked_players_page,  # Add this to the context
        'leaderboards': leaderboard_list_of_dict,
    }

    return render(request, 'leaderboards/ranked_combat_leaderboard.html', context)

def ranked_matches(request):
    # Fetch top 20 players based on ELO
    top_players = RankedPlayer.objects.order_by('-elo_duelsx')[:20]

    # Initialize dictionary for ELO histories
    elo_histories = {}

    # Loop through each top player and fetch their duel history
    for player in top_players:
        player_duels = Duel.objects.filter(
            Q(winner_playfabid=player.playfabid) | Q(loser_playfabid=player.playfabid)
        ).order_by('timestamp').values('timestamp', 'winner_playfabid', 'winner_elo', 'loser_playfabid', 'loser_elo')

        elo_history = []
        for duel in player_duels:
            timestamp_formatted = DateFormat(duel['timestamp']).format('c')  # ISO format
            if duel['winner_playfabid'] == player.playfabid:
                elo_history.append({'timestamp': timestamp_formatted, 'elo': duel['winner_elo']})
            elif duel['loser_playfabid'] == player.playfabid:
                elo_history.append({'timestamp': timestamp_formatted, 'elo': duel['loser_elo']})

        elo_histories[player.playfabid] = elo_history

    # Prepare match history data
    match_history_data = Duel.objects.all().order_by('-timestamp')
    playfabids = set([match.winner_playfabid for match in match_history_data] + 
                     [match.loser_playfabid for match in match_history_data])
    players = Player.objects.filter(playfabid__in=playfabids).in_bulk(field_name='playfabid')

    enhanced_match_data = []
    for match in match_history_data:
        winner_player = players.get(match.winner_playfabid)
        loser_player = players.get(match.loser_playfabid)
        enhanced_match = {
            'timestamp': match.timestamp,
            'winner_name': winner_player.most_common_alias() if winner_player else match.winner_playfabid,
            'winner_score': match.winner_score,
            'loser_name': loser_player.most_common_alias() if loser_player else match.loser_playfabid,
            'loser_score': match.loser_score,
            'winner_url': f'/leaderboards/player/{match.winner_playfabid}',
            'loser_url': f'/leaderboards/player/{match.loser_playfabid}'
        }
        enhanced_match_data.append(enhanced_match)

    # Convert elo_histories to JSON
    elo_histories_json = json.dumps(elo_histories)

    context = {
        'match_history_data': enhanced_match_data,
        'elo_histories_json': elo_histories_json,  # Pass the JSON string
        'leaderboards': leaderboard_list_of_dict,
    }

    return render(request, 'leaderboards/ranked_matches.html', context)




def player_progress_over_time(request, source_table='GlobalXp'):
    source_table = request.GET.get('table_name', default='GlobalXp')  # Replace 'default_table_name' with your default table name
    if source_table not in leaderboards:
        return HttpResponseBadRequest("Invalid source table name")
    playfab_ids_input = request.GET.get('playfabids')  # Example: 'id1,id2,id3'
    playfab_ids = playfab_ids_input.split(',') if playfab_ids_input else []
    playfab_ids_filter = f"AND playfabid IN ({','.join(['%s' for _ in playfab_ids])})" if playfab_ids else ""
    query = f"""
    WITH RecentSerialNumbers AS (
        SELECT DISTINCT LEFT(CAST(serialnumber AS TEXT), 8) AS date_part, serialnumber
        FROM {source_table}
        ORDER BY serialnumber DESC
        LIMIT 60
    ),
    SourceTableIncrements AS (
        SELECT
            playfabid,
            LEFT(CAST(serialnumber AS TEXT), 8) AS date_part,
            LEAD(stat_value) OVER (PARTITION BY playfabid ORDER BY serialnumber) - stat_value AS source_increment
        FROM {source_table}
        WHERE LEFT(CAST(serialnumber AS TEXT), 8) IN (SELECT date_part FROM RecentSerialNumbers)
        {playfab_ids_filter}
    ),
    TotalSourceGains AS (
        SELECT
            playfabid,
            SUM(source_increment) AS total_source_gain
        FROM SourceTableIncrements
        GROUP BY playfabid
    ),
    TopPlayers AS (
        SELECT playfabid
        FROM TotalSourceGains
        ORDER BY total_source_gain DESC
        LIMIT 300
    ),
    PlaytimeIncrements AS (
        SELECT
            playfabid,
            LEFT(CAST(serialnumber AS TEXT), 8) AS date_part,
            LEAD(stat_value) OVER (PARTITION BY playfabid ORDER BY serialnumber) - stat_value AS playtime_increment
        FROM playtimeex
        WHERE playfabid IN (SELECT playfabid FROM TopPlayers)
        AND LEFT(CAST(serialnumber AS TEXT), 8) IN (SELECT date_part FROM RecentSerialNumbers)
    )
    SELECT
        p.playfabid,
        p.date_part,
        p.playtime_increment,
        s.source_increment
    FROM PlaytimeIncrements p
    JOIN SourceTableIncrements s ON p.playfabid = s.playfabid AND p.date_part = s.date_part
    WHERE p.playtime_increment IS NOT NULL AND s.source_increment IS NOT NULL
    ORDER BY p.playfabid, p.date_part;
    """
    with connection.cursor() as cursor:
        if playfab_ids:
            cursor.execute(query, playfab_ids)
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
    playfabids = [row[0] for row in rows]
    players = Player.objects.filter(playfabid__in=playfabids, badlist=False).in_bulk(field_name='playfabid')
    grouped_data = defaultdict(list)
    max_gains_dict = {}

    for row in rows:
        player = players.get(row[0])
        if player:
            formatted_date = row[1][:4] + '-' + row[1][4:6] + '-' + row[1][6:8]
            gain_data = {
                'date': formatted_date,
                'source_increment': row[3],
                'playtime_increment': row[2]
            }
            grouped_data[player.most_common_alias()].append(gain_data)
            if player.most_common_alias() not in max_gains_dict or gain_data['source_increment'] > max_gains_dict[player.most_common_alias()]['source_increment']:
                max_gains_dict[player.most_common_alias()] = gain_data
    max_gains = sorted(max_gains_dict.items(), key=lambda x: x[1]['source_increment'], reverse=True)
    json_data = json.dumps(grouped_data)
    return render(request, 'leaderboards/player_progress.html', {
        'leaderboards': leaderboard_list_of_dict, 
        'data': json_data, 
        'max_gains': max_gains,
        'valid_table_names': leaderboards,
        'table_name': source_table,
        'playfab_ids_input': playfab_ids_input,
    })

def merged_leaderboard_view(request):
    latest_serial_number_daily = DailyPlaytime.objects.latest('serialnumber').serialnumber
    latest_serial_number_ex = PlaytimeEx.objects.latest('serialnumber').serialnumber

    playtime_data = DailyPlaytime.objects.filter(serialnumber=latest_serial_number_daily).values('playfabid').annotate(total_playtime=Sum('stat_value'))
    playtimeex_data = PlaytimeEx.objects.filter(serialnumber=latest_serial_number_ex).values('playfabid').annotate(total_playtime=Sum('stat_value'))
    combined_data = {}
    for entry in list(playtime_data) + list(playtimeex_data):
        key = entry['playfabid']
        combined_data[key] = combined_data.get(key, 0) + entry['total_playtime']
    sorted_combined_data = sorted(combined_data.items(), key=lambda x: x[1], reverse=True)[:1000] #LIMIT TO TOP 1000 HERE.
    playfabids = [key for key, _ in sorted_combined_data]
    players = Player.objects.filter(playfabid__in=playfabids).in_bulk(field_name='playfabid')

    merged_leaderboard = []
    for playfabid, total_playtime in sorted_combined_data:
        player = players.get(playfabid)
        if player:
            merged_leaderboard.append({
                'playfabid': playfabid,
                'player_name': player.most_common_alias(), 
                'total_playtime': total_playtime,
                'profile_url': f'/leaderboards/player/{playfabid}'
            })
    context = {'merged_leaderboard': merged_leaderboard}
    return render(request, 'leaderboards/merged_leaderboard_view.html', context)

def get_meta_sumstats(request):
    latest_entry = ChivstatsSumstats.objects.order_by('-serial_date').first()
    context = {
        'latest_entry': latest_entry,
        'unique_players': latest_entry.unique_players,
        'daily_players': latest_entry.daily_players,
    }
    for class_name in leaderboard_classes:
        ModelClass = apps.get_model('leaderboards', class_name)
        latest_data = ModelClass.objects.order_by('-serialnumber').first()
        context[f"{class_name.lower()}_latest"] = latest_data.stat_value if latest_data else None
    return render(request, 'leaderboards/meta_sumstats.html', context)

def show_games(request):
    with open('/tmp/currentgames', 'r') as f:
        data = json.load(f)
    reader = Reader('/home/webchiv/GeoLite2-City.mmdb')
    for game in data['Data']['Games']:
        try:
            response = reader.city(game['ServerIPV4Address'])
            game['Location'] = f"{response.city.name}, {response.subdivisions.most_specific.iso_code}"
        except AddressNotFoundError:
            game['Location'] = "Unknown"
        except GeoIP2Error:
            game['Location'] = "Error"

    populated_server_count = 0
    for game in data['Data']['Games']:
        if len(game['PlayerUserIds']) > 0:
            populated_server_count += 1
    context = {
        'data': data,
        'leaderboards': leaderboard_list_of_dict,
        'populated_server_count': populated_server_count
    }

    return render(request, 'leaderboards/show_games.html', context)

def get_leaderboards_context():
    return {'leaderboards': leaderboard_list_of_dict}

def get_hourly_player_count(request):
    if request.path.endswith('/api/hourly-player-count/'):
        data = list(HourlyPlayerCount.objects.filter(player_count__gte=0).values('timestamp_hour', 'player_count'))
        return JsonResponse(data, safe=False)
    else:
        context = get_leaderboards_context()
        return render(request, 'leaderboards/hourly_graph.html', context)

from django.shortcuts import render
from .models import HourlyPlayerCount
from django.db.models import F, Window, ExpressionWrapper, fields, Case, When
from django.db.models.functions import Lag, ExtractHour
from django.http import JsonResponse
from django.db.models import Case, When, Value, IntegerField
from django.db.models import Window, F
from django.db.models.functions import Lag, ExtractHour
from django.db.models.expressions import ExpressionWrapper
from django.db.models.fields import FloatField
from django.http import JsonResponse
from .models import HourlyPlayerCount
from django.db.models.functions import Round

def get_daily_unique_accounts(request):
    # Annotate all data with the hour extracted from timestamp_hour
    all_data_with_hour = HourlyPlayerCount.objects.annotate(
        hour=ExtractHour('timestamp_hour'),
    )

    # Annotate with the previous day's player count and the calculated gain
    data = all_data_with_hour.annotate(
        previous_day_count=Window(
            expression=Lag('player_count', default=None),
            order_by=F('timestamp_hour').asc()
        ),
        gain=F('player_count') - F('previous_day_count'),
    ).annotate(
        percent_gain=Case(
            # Calculate percentage gain only when previous_day_count is not zero
            When(previous_day_count=0, then=Value(None)),
            default=ExpressionWrapper(
                F('gain') * 100.0 / F('previous_day_count'),
                output_field=FloatField()
            ),
        )
    ).filter(hour=23).values(
        'timestamp_hour', 'player_count', 'gain', 'percent_gain'
    ).order_by('timestamp_hour')  # Order by ascending to get oldest to newest

    # Get the last 14 days of data for the table, need to retain all values for the line chart above.
    last_14_days_data = data.order_by('-timestamp_hour')[:14]

    if request.path.endswith('/api/daily-unique-accounts/'):
        return JsonResponse(list(data), safe=False)
    else:
        context = {
            'all_data': list(data),
            'last_14_days_data': list(last_14_days_data),
            # ... include other context data as needed ...
        }
        context.update(get_leaderboards_context())
        return render(request, 'leaderboards/daily_unique_accounts_graph.html', context)



def tattle(request):
    players = Player.objects.filter(badlist=True)
    player_data = []
    for player in players:
        player_data.append({
            'playfabid': player.playfabid,
            'badlist_reason': player.badlist_reason,
            'badlist_timestamp': player.badlist_timestamp,
            'most_common_alias': player.most_common_alias(),
        })
    context = {
        'players': player_data,
    }
    return render(request, 'leaderboards/tattle.html', context)

def player_search(request):
    search_query = request.GET.get('search_query', '').strip()
    
    # Check if the search query matches the PlayerID pattern
    if re.match(r'^[A-F0-9]{16}$', search_query):
        # Redirect to the player's profile if it's a valid PlayerID
        return redirect('leaderboards:player_profile', playfabid=search_query)

    players = []
    if search_query:
        players = Player.objects.filter(alias_history__icontains=search_query)
        players_data = []
        for player in players:
            last_seen_formatted = None
            if player.lastseen_serial:
                last_seen_formatted = datetime.strptime(str(player.lastseen_serial)[:8], '%Y%m%d').strftime('%Y-%m-%d')
            players_data.append({
                'playfabid': player.playfabid,
                'name': player.most_common_alias(),
                'last_seen': last_seen_formatted or 'Never'
            })
        players = sorted(players_data, key=lambda x: (x['last_seen'] != 'Never', x['last_seen']), reverse=True)

    context = {
        'players': players,
        'search_query': search_query,
        'leaderboards': leaderboard_list_of_dict,
    }
    return render(request, 'leaderboards/player_search.html', context)

def format_last_seen(last_seen_serial):
    if last_seen_serial:
        last_seen_str = str(last_seen_serial)
        formatted_date = datetime.strptime(last_seen_str[:8], '%Y%m%d').strftime('%Y-%m-%d')
        return formatted_date
    else:
        return 'Never'

def leaderboard_name_to_url(leaderboard_name):
    if leaderboard_name.startswith('ExperienceWeapon'):
        leaderboard_name = leaderboard_name.replace('ExperienceWeapon', '')
    return re.sub(r'(?<!^)([A-Z])', r'-\1', leaderboard_name).lower()

def url_to_leaderboard_name(url):
    formatted_url = url.replace('-', ' ').title().replace(' ', '')
    if not any(formatted_url.startswith(word) for word in
               ['GlobalXp', 'Playtime', 'PlaytimeEx' 'DailyPlaytime', 'ExperienceArcher', 'ExperienceFootman', 'ExperienceVanguard',
                'ExperienceKnight']):
        formatted_url = 'ExperienceWeapon' + formatted_url
    return formatted_url

def get_top_gainers(time_period, table_name, page=1, items_per_page=50):
    cache_key = f'top_gainers_{time_period}_{table_name}_{page}_{items_per_page}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    offset = (page - 1) * items_per_page
    sql_query = f"""
    WITH DailyMaxExperience AS (
        SELECT
            playfabid,
            TO_DATE(LEFT(CAST(serialnumber AS TEXT), 8), 'YYYYMMDD') AS date,
            MAX(stat_value) AS max_stat_value_per_day
        FROM {table_name}
        WHERE TO_DATE(LEFT(CAST(serialnumber AS TEXT), 8), 'YYYYMMDD') >= CURRENT_DATE - INTERVAL '{time_period} days'
        GROUP BY playfabid, date
        ORDER BY playfabid, date
    ),
    DailyGains AS (
        SELECT 
            playfabid,
            date,
            max_stat_value_per_day - LAG(max_stat_value_per_day, 1) OVER (PARTITION BY playfabid ORDER BY date) AS daily_gain
        FROM DailyMaxExperience
    ),
    TotalGains AS (
        SELECT
            playfabid,
            SUM(daily_gain) AS total_gain
        FROM DailyGains
        WHERE daily_gain IS NOT NULL
        GROUP BY playfabid
        ORDER BY total_gain DESC
        LIMIT 250
    )
    SELECT
        TotalGains.playfabid,
        total_gain
    FROM TotalGains
    """

    with connection.cursor() as cursor:
        cursor.execute(sql_query)
        results = cursor.fetchall()
        column_names = [col[0] for col in cursor.description]
        leaderboard_data = [
            dict(zip(column_names, row))
            for row in results
        ]
    cache.set(cache_key, leaderboard_data, 3600)
    return leaderboard_data

def top_gainers_leaderboard(request):
    page = int(request.GET.get('page', 1))
    time_period = request.GET.get('time_period', '7')
    table_name = request.GET.get('table_name', 'experienceknight')
    valid_time_periods = ['2', '7', '14', '30']
    valid_table_names = [
        ("globalxp", "Global XP"),
        ("playtime", "Playtime"),
        ("playtimeex", "Playtime Ex"),
        ("dailyplaytime", "Daily Playtime"),
        ("experiencearcher", "Experience Archer"),
        ("experiencefootman", "Experience Footman"),
        ("experiencevanguard", "Experience Vanguard"),
        ("experienceknight", "Experience Knight"),
        ("experienceweaponmorningstar", "Experience Weapon Morning Star"),
        ("experienceweaponheavycavalrysword", "Experience Weapon Heavy Cavalry Sword"),
        ("experienceweaponthrowingmallet", "Experience Weapon Throwing Mallet"),
        ("experienceweapondagger", "Experience Weapon Dagger"),
        ("experienceweaponmediumshield", "Experience Weapon Medium Shield"),
        ("experienceweaponheavyshield", "Experience Weapon Heavy Shield"),
        ("experienceweaponwarbow", "Experience Weapon War Bow"),
        ("experienceweaponshovel", "Experience Weapon Shovel"),
        ("experienceweaponquarterstaff", "Experience Weapon Quarterstaff"),
        ("experienceweaponrapier", "Experience Weapon Rapier"),
        ("experienceweaponwarhammer", "Experience Weapon War Hammer"),
        ("experienceweaponthrowingaxe", "Experience Weapon Throwing Axe"),
        ("experienceweaponexecutionersaxe", "Experience Weapon Executioner's Axe"),
        ("experienceweaponcrossbow", "Experience Weapon Crossbow"),
        ("experienceweaponpolehammer", "Experience Weapon Pole Hammer"),
        ("experienceweaponaxe", "Experience Weapon Axe"),
        ("experienceweaponheavymace", "Experience Weapon Heavy Mace"),
        ("experienceweaponbow", "Experience Weapon Bow"),
        ("experienceweaponknife", "Experience Weapon Knife"),
        ("experienceweaponpickaxe", "Experience Weapon Pick Axe"),
        ("experienceweaponcudgel", "Experience Weapon Cudgel"),
        ("experienceweaponfalchion", "Experience Weapon Falchion"),
        ("experienceweaponwarclub", "Experience Weapon War Club"),
        ("experienceweaponspear", "Experience Weapon Spear"),
        ("experienceweaponshortsword", "Experience Weapon Short Sword"),
        ("experienceweapononehandedspear", "Experience Weapon One-Handed Spear"),
        ("experienceweaponlance", "Experience Weapon Lance"),
        ("experienceweaponbattleaxe", "Experience Weapon Battle Axe"),
        ("experienceweaponglaive", "Experience Weapon Glaive"),
        ("experienceweaponmace", "Experience Weapon Mace"),
        ("experienceweaponhalberd", "Experience Weapon Halberd"),
        ("experienceweaponhighlandsword", "Experience Weapon Highland Sword"),
        ("experienceweaponpoleaxe", "Experience Weapon Pole Axe"),
        ("experienceweaponkatars", "Experience Weapon Katars"),
        ("experienceweaponmaul", "Experience Weapon Maul"),
        ("experienceweapondaneaxe", "Experience Weapon Dane Axe"),
        ("experienceweaponbastardsword", "Experience Weapon Bastard Sword"),
        ("experienceweaponjavelin", "Experience Weapon Javelin"),
        ("experienceweapongreatsword", "Experience Weapon Greatsword"),
        ("experienceweaponsword", "Experience Weapon Sword"),
        ("experienceweaponsledgehammer", "Experience Weapon Sledge Hammer"),
        ("experienceweaponlightshield", "Experience Weapon Light Shield"),
        ("experienceweapontwohandedhammer", "Experience Weapon Two-Handed Hammer"),
        ("experienceweaponhatchet", "Experience Weapon Hatchet"),
        ("experienceweaponwaraxe", "Experience Weapon War Axe"),
        ("experienceweaponthrowingknife", "Experience Weapon Throwing Knife"),
        ("experienceweaponmesser", "Experience Weapon Messer"),
        ("experienceweaponheavycrossbow", "Experience Weapon Heavy Crossbow")
    ]
    leaderboard_data = get_top_gainers(time_period, table_name, page)

    for entry in leaderboard_data:
        playfabid = entry['playfabid']
        player = Player.objects.get(playfabid=playfabid)
        entry['most_common_alias'] = player.most_common_alias()
    error_message = None
    if time_period not in valid_time_periods or table_name not in [x[0] for x in valid_table_names]:
        error_message = 'Invalid parameters'
    context = {
        'leaderboard_data': leaderboard_data,
        'leaderboards': leaderboard_list_of_dict,
        'time_period': time_period,
        'table_name': table_name,
        'table_names': valid_table_names,
        'error_message': error_message
    }
    
    return render(request, 'leaderboards/top_gainers_leaderboard.html', context)


from django.shortcuts import render
from datetime import datetime
from .models import ChivstatsSumstats, HourlyPlayerCount
from django.db.models.functions import ExtractHour, Lag
from django.db.models import Window, F, ExpressionWrapper, fields, Case, When
from .utils import read_yaml_news  # Assuming you have a utility function to read news
from django.db.models import Sum, Count
from django.db.models.functions import TruncDay
from django.utils.timezone import now
from datetime import timedelta

def index(request):
    latest_entry = ChivstatsSumstats.objects.latest('serial_date')
    latest_update = datetime.strptime(str(latest_entry.serial_date), '%Y%m%d')
    news = read_yaml_news()
    news.sort(reverse=True, key=lambda x : x['date'])

    # Fetch data for the daily unique accounts chart and table
    all_data_with_hour = HourlyPlayerCount.objects.annotate(
        hour=ExtractHour('timestamp_hour'),
    )

    # Annotate with the previous day's player count and the calculated gain
    data = all_data_with_hour.annotate(
        previous_day_count=Window(
            expression=Lag('player_count', default=None),
            order_by=F('timestamp_hour').asc()
        ),
        gain=F('player_count') - F('previous_day_count'),
    ).annotate(
        percent_gain=Case(
            # Calculate percentage gain only when previous_day_count is not zero
            When(previous_day_count=0, then=Value(None)),
            default=ExpressionWrapper(
                F('gain') * 100.0 / F('previous_day_count'),
                output_field=fields.FloatField()
            ),
        )
    ).filter(hour=23).values(
        'timestamp_hour', 'player_count', 'gain', 'percent_gain'
    ).order_by('-timestamp_hour')

    # Get the last 14 days of data for the table
    last_14_days_data = list(data[:14])

    duels_last_14_days = Duel.objects.filter(
        timestamp__gte=now() - timedelta(days=14)
    ).annotate(
        day=TruncDay('timestamp')
    ).values('day').annotate(
        total_duels=Count('id'),
        total_kills=Sum(Case(
            When(winner_score__isnull=False, then='winner_score'),
            default=Value(0)
        )) + Sum(Case(
            When(loser_score__isnull=False, then='loser_score'),
            default=Value(0)
        )),
        registered_players=Count('winner_playfabid', distinct=True) +
                            Count('loser_playfabid', distinct=True)
    ).order_by('-day')

    # Convert QuerySet to list of dicts
    ranked_combat_stats = list(duels_last_14_days)


    context = {
        'leaderboards': leaderboard_list_of_dict,  # This needs to be defined or fetched as well
        'latest_entry': latest_entry,
        'latest_update': latest_update,
        'news': news,
        'all_data': list(data),
        'ranked_combat_stats': ranked_combat_stats,
        'last_14_days_data': last_14_days_data,  # Add this for the table in the template
    }

    return render(request, 'leaderboards/index.html', context)


def leaderboard(request, leaderboard_name):
    leaderboard_name = leaderboard_name.replace(' ', '')
    search_query = request.GET.get('search_query', '')
    page_number = request.GET.get('page', 1)
    results_per_page = request.GET.get('results_per_page', 50)
    show_recent_players = request.GET.get('recent_players') == 'on'
    hard_coded_date = 20231107 #HARDCODED DATE OF RECENT PATCH
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1
    try:
        results_per_page = int(results_per_page)
    except ValueError:
        results_per_page = 50
    if leaderboard_name not in leaderboards:
        raise Http404("Leaderboard does not exist")
    latest_serial_number = LatestLeaderboard.objects.get(leaderboard_name=leaderboard_name).serialnumber
    players_with_badlist = Player.objects.filter(badlist=True).values_list('playfabid', flat=True)
    leaderboard_model = apps.get_model(app_label='leaderboards', model_name=leaderboard_name)
    leaderboard_data_query = leaderboard_model.objects.filter(serialnumber=latest_serial_number).select_related('playfabid').exclude(playfabid__in=players_with_badlist).order_by('-stat_value')
    if show_recent_players:
        leaderboard_data_query = leaderboard_data_query.filter(playfabid__lastseen_serial__gt=hard_coded_date)
    if search_query:
        leaderboard_data_query = leaderboard_data_query.filter(playfabid__alias_history__icontains=search_query)
    paginator = Paginator(leaderboard_data_query, results_per_page)
    page_obj = paginator.get_page(page_number)
    latest_update = datetime.strptime(str(latest_serial_number), "%Y%m%d%H%M")
    leaderboard_data = [{'player': entry.playfabid.playfabid,
                         'alias': entry.playfabid.most_common_alias(),
                         'value': entry.stat_value,
                         'rank': i + 1 + ((page_obj.number - 1) * results_per_page)}
                        for i, entry in enumerate(page_obj)]
    context = {
        'leaderboard_data': leaderboard_data,
        'page_obj': page_obj,
        'leaderboard_name_url': (leaderboard_name),
        'leaderboard_name': humanize_leaderboard_name(leaderboard_name),
        'latest_update': latest_update,
        'leaderboards': leaderboard_list_of_dict,
        'search_query': search_query,
        'show_recent_players': show_recent_players,
    }
    return render(request, 'leaderboards/leaderboard.html', context)

def get_leaderboard_data(leaderboard_name, page_number, results_per_page=50, search_query=''):
    if leaderboard_name not in leaderboards:
        raise Http404("Leaderboard does not exist")
    leaderboard_model = apps.get_model(app_label='leaderboards', model_name=leaderboard_name)
    latest_serial_number = LatestLeaderboard.objects.get(leaderboard_name=leaderboard_name).serialnumber
    players_with_badlist = Player.objects.filter(badlist=True).values_list('playfabid', flat=True)
    leaderboard_data = leaderboard_model.objects.filter(serialnumber=latest_serial_number).select_related(
        'playfabid').exclude(playfabid__in=players_with_badlist).order_by('-stat_value')
    if search_query:
        leaderboard_data = leaderboard_data.filter(playfabid__alias_history__icontains=search_query)
    paginator = Paginator(leaderboard_data, results_per_page)
    page_obj = paginator.get_page(page_number)
    latest_update = datetime.strptime(str(latest_serial_number), "%Y%m%d%H%M")
    leaderboard_data_full = [{'player': entry.playfabid.playfabid,
                              'alias': entry.playfabid.most_common_alias(),
                              'value': entry.stat_value,
                              'rank': i + 1}
                             for i, entry in enumerate(leaderboard_data)]
    leaderboard_data = [{'player': entry.playfabid.playfabid,
                         'alias': entry.playfabid.most_common_alias(),
                         'value': entry.stat_value,
                         'rank': i + 1 + ((page_obj.number - 1) * results_per_page)}
                        for i, entry in enumerate(page_obj)]
    for entry in leaderboard_data:
        entry['rank'] = next((item['rank'] for item in leaderboard_data_full if
                              item['player'] == entry['player']), entry['rank'])
    return leaderboard_data, page_obj, latest_update

def player_profile(request, playfabid):
    context = {}
    try:
        player = Player.objects.get(playfabid=playfabid)
        ranked_player = RankedPlayer.objects.filter(playfabid=playfabid).first()
    except Player.DoesNotExist:
        raise Http404("Player does not exist")

    if player.badlist:  # Check if the player is blocked
        # Render a template or return a response indicating the player is blocked
        context = {'message': 'This player is blocked.'}
        return render(request, 'leaderboards/blocked_player.html', context)

    leaderboard_data = []
    latest_serial_numbers = {}

    for leaderboard_name in leaderboards:
        leaderboard_model = getattr(models, leaderboard_name)
        latest_serial_number = LatestLeaderboard.objects.get(leaderboard_name=leaderboard_name).serialnumber
        latest_serial_numbers[leaderboard_name] = latest_serial_number
        leaderboard_entry = leaderboard_model.objects.filter(
            playfabid=player,
            serialnumber=latest_serial_number
        ).first()
        if leaderboard_entry:
            stat_value = leaderboard_entry.stat_value
            rank = leaderboard_model.objects.filter(
                serialnumber=latest_serial_number,
                stat_value__gt=stat_value
            ).count() + 1
            level, total_gold = calculate_level_and_gold(stat_value)
            leaderboard_data.append({
                'leaderboard_name': leaderboard_name,
                'stat_value': stat_value,
                'rank': rank,
                'title': humanize_leaderboard_name(leaderboard_name),
                'level': level,
                'total_gold': total_gold, 
            })

    player = Player.objects.get(playfabid=playfabid)
    alias_recent = player.alias_recent or "No recent alias recorded"
    playtime_data = []
    today = datetime.now().date()
    for i in range(14):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y%m%d")
        highest_stat_value = DailyPlaytime.objects.filter(
            playfabid=playfabid,
            serialnumber__startswith=date_str
        ).aggregate(Max('stat_value'))['stat_value__max']
        if highest_stat_value is not None:
            playtime_data.append({
                'date': date.strftime("%B %d, %Y"),
                'playtime': highest_stat_value,
            })

    if ranked_player:
        # Calculate ranks
        elo_rank = RankedPlayer.objects.annotate(rank=Window(
            expression=Rank(),
            order_by=F('elo_duelsx').desc()
        )).get(playfabid=playfabid).rank

        kdr_rank = RankedPlayer.objects.annotate(
            kdr=Case(
                When(deaths=0, then=None),  # Use None for cases where deaths are zero
                default=ExpressionWrapper(F('kills') / F('deaths'), output_field=FloatField()),
                output_field=FloatField()
            ),
            rank=Window(
                expression=Rank(),
                order_by=F('kdr').desc(nulls_last=True)
            )
        ).get(playfabid=playfabid).rank

        matches_rank = RankedPlayer.objects.annotate(rank=Window(
            expression=Rank(),
            order_by=F('matches').desc()
        )).get(playfabid=playfabid).rank
        deaths_rank = RankedPlayer.objects.annotate(rank=Window(
            expression=Rank(),
            order_by=F('kills').desc()
        )).get(playfabid=playfabid).rank
        kills_rank = RankedPlayer.objects.annotate(rank=Window(
            expression=Rank(),
            order_by=F('deaths').desc()
        )).get(playfabid=playfabid).rank

        ranked_data = {
            'elo_rating': ranked_player.elo_duelsx,
            'matches': ranked_player.matches,
            'kills': ranked_player.kills,
            'deaths': ranked_player.deaths,
            'discord_username': ranked_player.discord_username,
            'common_name': ranked_player.common_name,
            'gamename': ranked_player.gamename,
            'elo_rank': elo_rank,
            'kdr_rank': kdr_rank if kdr_rank is not None else 'N/A',
            'matches_rank': matches_rank,
            'kills_rank': kills_rank,
            'deaths_rank': deaths_rank,            
        }
    else:
        ranked_data = None

    context.update({
        'playfabid': playfabid,
        'alias_recent': alias_recent,
        'player': player,
        'aliases': player.aliases(),
        'leaderboard_data': leaderboard_data,
        'latest_serial_numbers': latest_serial_numbers,
        'leaderboards': leaderboard_list_of_dict,
        'playtime_data': playtime_data,
        'ranked_data': ranked_data,
    })
    return render(request, 'leaderboards/playerprofile.html', context)

def top_players_by_playtime(request):
    today = datetime.now().date()
    seven_days_ago = today - timedelta(days=7)
    top_players = DailyPlaytime.objects.filter(
        serialnumber__gte=seven_days_ago.strftime("%Y%m%d")
    ).values('playfabid').annotate(average_playtime=Avg('stat_value')).order_by('-average_playtime')[:10]
    player_data = []
    for player in top_players:
        playfabid = player['playfabid']
        average_playtime = player['average_playtime']
        player_data.append({
            'playfabid': playfabid,
            'average_playtime': average_playtime,
            'most_common_alias': Player.objects.get(playfabid=playfabid).most_common_alias(),
        })
    context = {
        'players': player_data,
    }
    return render(request, 'leaderboards/top_players.html', context)

def go_touch_grass_leaderboard(request):
    leaderboard_name = 'meta_averagedailyplaytime'
    search_query = request.GET.get('search_query', '')
    page_number = request.GET.get('page', 1)
    results_per_page = request.GET.get('results_per_page', 50)
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1
    try:
        results_per_page = int(results_per_page)
    except ValueError:
        results_per_page = 50
    leaderboard_data, page_obj, latest_update = get_leaderboard_data(leaderboard_name, page_number, results_per_page, search_query)
    context = {
        'leaderboard_data': leaderboard_data,
        'page_obj': page_obj,
        'leaderboard_name': 'Go Touch Grass Leaderboard',
        'latest_update': latest_update,
        'leaderboards': leaderboard_list_of_dict,
        'search_query': search_query,
    }
    return render(request, 'leaderboards/go_touch_grass_leaderboard.html', context)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000
class PlayerListAPIView(generics.ListAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    pagination_class = StandardResultsSetPagination
class LatestLeaderboardPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
class LatestLeaderboardListAPIView(generics.ListAPIView):
    queryset = LatestLeaderboard.objects.all().order_by('-serialnumber')
    serializer_class = LatestLeaderboardSerializer
    pagination_class = LatestLeaderboardPagination
from django.core.exceptions import ObjectDoesNotExist

@api_view(['GET'])
def get_leaderboard(request):
    leaderboard_name = request.GET.get('leaderboard_name')
    serializer_class_name = f"{leaderboard_name}Serializer"
    serializer_class = globals().get(serializer_class_name)  
    if serializer_class:
        try:
            model_class = globals()[leaderboard_name]
            data = model_class.objects.all()
            paginator = PageNumberPagination()
            paginated_data = paginator.paginate_queryset(data, request)
            serializer = serializer_class(paginated_data, many=True)
            return paginator.get_paginated_response(serializer.data)
        except ObjectDoesNotExist:
            return Response({'error': f'{leaderboard_name} does not exist'}, status=404)
        except Exception as e:
            return Response({'error': 'An error occurred while processing the request'}, status=500)
    return Response({'error': 'Invalid leaderboard_name'}, status=400)


class LeaderboardListAPIView(generics.ListAPIView):
    serializer_class = LeaderboardSerializer

    def get_queryset(self):
        leaderboard_name = self.request.query_params.get('leaderboard_name', None)
        if leaderboard_name is not None:
            leaderboard_model = globals().get(f"{leaderboard_name}Leaderboard", Leaderboard)
            latest_serial_number = leaderboard_model.objects.latest('serialnumber').serialnumber
            return leaderboard_model.objects.filter(serialnumber=latest_serial_number)
        return Leaderboard.objects.none()
