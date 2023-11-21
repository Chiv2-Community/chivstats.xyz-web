import re, json
from copy import copy
from datetime import datetime, timedelta

from django.apps import apps
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import connection
from django.db.models import Avg, Max
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page

from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from leaderboards import models
from .models import Leaderboard, Player, HourlyPlayerCount, ChivstatsSumstats, DailyPlaytime, leaderboard_classes
# import the leaderboard List since it should be defined just in one place
from .models import (leaderboard_classes, LatestLeaderboard, ChivstatsSumstats)
from .serializers import (LatestLeaderboardSerializer, PlayerSerializer)
from .serializers import LeaderboardSerializer
from .utils import (humanize_leaderboard_name, organize_sidebar, create_leaderboard_list, read_yaml_news, to_json)

leaderboards = copy(leaderboard_classes);
#For now simple alphabetical order
leaderboards.sort(key=organize_sidebar);
#list of dicts of url and readable text
leaderboard_list_of_dict = create_leaderboard_list()

from geoip2.database import Reader
from geoip2.errors import AddressNotFoundError, GeoIP2Error

def get_meta_sumstats(request):
    latest_entry = ChivstatsSumstats.objects.order_by('-serial_date').first()

    # Initialize a dictionary to hold the context
    context = {
        'latest_entry': latest_entry,
        'unique_players': latest_entry.unique_players,
        'daily_players': latest_entry.daily_players,
    }

    # Loop through the leaderboard classes to fetch the latest data for each
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
        if len(game['PlayerUserIds']) > 0:  # Adjust this condition based on how you determine if a server is populated
            populated_server_count += 1

    # Include the leaderboards and the populated_server_count in the context
    context = {
        'data': data,
        'leaderboards': leaderboard_list_of_dict,  # This is the line you'll want to add
        'populated_server_count': populated_server_count  # Add this line to include the populated_server_count
    }

    return render(request, 'leaderboards/show_games.html', context)

def get_leaderboards_context():
    return {'leaderboards': leaderboard_list_of_dict}

def get_hourly_player_count(request):
    if request.path.endswith('/api/hourly-player-count/'):
        data = list(HourlyPlayerCount.objects.filter(player_count__gte=0).values('timestamp_hour', 'player_count'))
        return JsonResponse(data, safe=False)
    else:
        context = get_leaderboards_context()  # Get the leaderboards context
        return render(request, 'leaderboards/hourly_graph.html', context)

def tattle(request):
    players = Player.objects.filter(badlist=True)
    player_data = []
    for player in players:
        player_data.append({
            'playfabid': player.playfabid,  # Include the playfabid field
            'badlist_reason': player.badlist_reason,
            'badlist_timestamp': player.badlist_timestamp,
            'most_common_alias': player.most_common_alias(),
        })
    context = {
        'players': player_data,
    }
    return render(request, 'leaderboards/tattle.html', context)

def player_search(request):
    search_query = request.GET.get('search_query', '')
    search_query = search_query.strip()
    if search_query:
        players = Player.objects.filter(alias_history__icontains=search_query)
        players = [{'playfabid': player.playfabid, 'name': player.most_common_alias()} for player in players]
    else:
        players = []
    context = {
        'players': players,
        'search_query': search_query,
        'leaderboards': leaderboard_list_of_dict,
    }
    return render(request, 'leaderboards/player_search.html', context)


#Is this used?  Can we remove?
def leaderboard_name_to_url(leaderboard_name):
    if leaderboard_name.startswith('ExperienceWeapon'):
        leaderboard_name = leaderboard_name.replace('ExperienceWeapon', '')
    return re.sub(r'(?<!^)([A-Z])', r'-\1', leaderboard_name).lower()

#is this used?
def url_to_leaderboard_name(url):
    formatted_url = url.replace('-', ' ').title().replace(' ', '')
    print(f'Formatted URL: {formatted_url}')  # Debugging line
    if not any(formatted_url.startswith(word) for word in
               ['GlobalXp', 'Playtime', 'PlaytimeEx' 'DailyPlaytime', 'ExperienceArcher', 'ExperienceFootman', 'ExperienceVanguard',
                'ExperienceKnight']):
        formatted_url = 'ExperienceWeapon' + formatted_url
    return formatted_url

def get_top_gainers(time_period, table_name, page=1, items_per_page=50):
    cache_key = f'top_gainers_{time_period}_{table_name}_{page}_{items_per_page}'  # Create a unique cache key
    cached_data = cache.get(cache_key)  # Try to get data from the cache

    if cached_data:
        return cached_data  # If cache exists, return it

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

        # Convert list of tuples to list of dictionaries
        column_names = [col[0] for col in cursor.description]
        leaderboard_data = [
            dict(zip(column_names, row))
            for row in results
        ]
    cache.set(cache_key, leaderboard_data, 3600)

    return leaderboard_data

# New view for the top gainers leaderboard
def top_gainers_leaderboard(request):
    page = int(request.GET.get('page', 1))  # Default to page 1
    time_period = request.GET.get('time_period', '7')  # Default to 7 days
    table_name = request.GET.get('table_name', 'experienceknight')  # Default to 'experienceknight'
    
    # Validate time_period and table_name against a pre-set list to prevent SQL injection
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

    # Fetch the most_common_alias for each playfabid
    for entry in leaderboard_data:
        playfabid = entry['playfabid']
        player = Player.objects.get(playfabid=playfabid)
        entry['most_common_alias'] = player.most_common_alias()

    error_message = None  # Initialize error_message as None (i.e., no error)
    
    if time_period not in valid_time_periods or table_name not in [x[0] for x in valid_table_names]:
        error_message = 'Invalid parameters'
    
    context = {
        'leaderboard_data': leaderboard_data,
        'leaderboards': leaderboard_list_of_dict,
        'time_period': time_period,
        'table_name': table_name,
        'table_names': valid_table_names,
        'error_message': error_message  # Add the error_message to the context
    }
    
    return render(request, 'leaderboards/top_gainers_leaderboard.html', context)

def index(request):
    latest_entry = ChivstatsSumstats.objects.latest('serial_date')
    latest_update = datetime.strptime(str(latest_entry.serial_date), '%Y%m%d')
    news = read_yaml_news()
    news.sort(reverse=True, key=lambda x : x['date'])
    context = {
        'leaderboards': leaderboard_list_of_dict,
        'latest_entry': latest_entry,
        'latest_update': latest_update,
        'news' : news
    }
    return render(request, 'leaderboards/index.html', context)

def leaderboard(request, leaderboard_name):
    leaderboard_name = leaderboard_name.replace(' ', '')  # Remove the space
    search_query = request.GET.get('search_query', '')
    page_number = request.GET.get('page', 1)
    results_per_page = request.GET.get('results_per_page', 50)
    show_recent_players = request.GET.get('recent_players') == 'on'
    hard_coded_date = 20231107

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
    try:
        player = Player.objects.get(playfabid=playfabid)
    except Player.DoesNotExist:
        raise Http404("Player does not exist")
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
            leaderboard_data.append({
                'leaderboard_name': leaderboard_name,
                'stat_value': stat_value,
                'rank': rank,
                'title': humanize_leaderboard_name(leaderboard_name),
            })
    playtime_data = []
    today = datetime.now().date()
    for i in range(1, 8):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y%m%d")
        highest_stat_value = leaderboard_model.objects.filter( # Changed from DailyPlaytime to leaderboard_model
            playfabid=player,
            playfabid__playfabid=playfabid,  # Filter for specific playfabid
            serialnumber__startswith=date_str
        ).aggregate(Max('stat_value'))['stat_value__max']
        if highest_stat_value:
            playtime_entry = leaderboard_model.objects.filter( # Changed from DailyPlaytime to leaderboard_model
                playfabid=player,
                playfabid__playfabid=playfabid,  # Filter for specific playfabid
                serialnumber__startswith=date_str,
                stat_value=highest_stat_value
            ).first()
            playtime_data.append({
                'date': date.strftime("%B %d, %Y"),
                'playtime': playtime_entry.stat_value,
            })
    #print(playtime_data)
    context = {
        'playfabid': playfabid,
        'player': player,
        'aliases': player.aliases(),
        'leaderboard_data': leaderboard_data,
        'latest_serial_numbers': latest_serial_numbers,
        'leaderboards': leaderboard_list_of_dict,
        'playtime_data': playtime_data,
    }
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
        
    # Log the leaderboard_name for debugging
    print(f'leaderboard_name: {leaderboard_name}')

    # Try to get the serializer class
    serializer_class_name = f"{leaderboard_name}Serializer"
    serializer_class = globals().get(serializer_class_name)

    # Log the serializer class for debugging
    print(f'serializer_class: {serializer_class}')
    
    if serializer_class:
        try:
            # Query the corresponding model
            model_class = globals()[leaderboard_name]
            data = model_class.objects.all()

            # Paginate the data
            paginator = PageNumberPagination()
            paginated_data = paginator.paginate_queryset(data, request)

            # Serialize the data
            serializer = serializer_class(paginated_data, many=True)

            return paginator.get_paginated_response(serializer.data)
        except ObjectDoesNotExist:
            return Response({'error': f'{leaderboard_name} does not exist'}, status=404)
        except Exception as e:
            # Catch any other exception and log it
            print(f'Error: {str(e)}')
            return Response({'error': 'An error occurred while processing the request'}, status=500)
    
    # Handle other cases or return an error if not found
    return Response({'error': 'Invalid leaderboard_name'}, status=400)


class LeaderboardListAPIView(generics.ListAPIView):
    serializer_class = LeaderboardSerializer

    def get_queryset(self):
        leaderboard_name = self.request.query_params.get('leaderboard_name', None)
        if leaderboard_name is not None:
            # Assuming that your dynamically created leaderboard models have a naming pattern {leaderboard_name}Leaderboard
            leaderboard_model = globals().get(f"{leaderboard_name}Leaderboard", Leaderboard)
            # Get the most recent serial number for the given leaderboard
            latest_serial_number = leaderboard_model.objects.latest('serialnumber').serialnumber
            # Filter the data based on the most recent serial number
            return leaderboard_model.objects.filter(serialnumber=latest_serial_number)
        return Leaderboard.objects.none()  # Return empty queryset if no leaderboard_name parameter
