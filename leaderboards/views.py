from datetime import datetime, timedelta
import re

from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.utils.text import slugify
from django.db.models import Avg, Max
from django.apps import apps
from django.http import HttpResponse, Http404
from rest_framework import generics, serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.decorators import api_view

from .serializers import (LatestLeaderboardSerializer, LeaderboardSerializer, PlayerSerializer)
from .models import (MetaAverageDailyPlaytime, ChivstatsSumstats, LatestLeaderboard, Leaderboard, Player, GlobalXp, Playtime, DailyPlaytime, ExperienceArcher,
                     MetaAverageDailyPlaytime, ExperienceFootman, ExperienceVanguard, ExperienceKnight, ExperienceWeaponMorningStar,
                     ExperienceWeaponHeavyCavalrySword, ExperienceWeaponThrowingMallet, ExperienceWeaponDagger,
                     ExperienceWeaponMediumShield, ExperienceWeaponHeavyShield, ExperienceWeaponWarBow,
                     ExperienceWeaponShovel, ExperienceWeaponQuarterstaff, ExperienceWeaponRapier,
                     ExperienceWeaponWarHammer, ExperienceWeaponThrowingAxe, ExperienceWeaponExecutionersAxe,
                     ExperienceWeaponCrossbow, ExperienceWeaponPoleHammer, ExperienceWeaponAxe,
                     ExperienceWeaponHeavyMace, ExperienceWeaponBow, ExperienceWeaponKnife,
                     ExperienceWeaponPickAxe, ExperienceWeaponCudgel, ExperienceWeaponFalchion, ExperienceWeaponWarClub, ExperienceWeaponSpear,
                     ExperienceWeaponShortSword, ExperienceWeaponOneHandedSpear, ExperienceWeaponLance,
                     ExperienceWeaponBattleAxe, ExperienceWeaponGlaive, ExperienceWeaponMace,
                     ExperienceWeaponHalberd, ExperienceWeaponHighlandSword, ExperienceWeaponPoleAxe, ExperienceWeaponKatars, ExperienceWeaponMaul, ExperienceWeaponDaneAxe,
                     ExperienceWeaponBastardSword, ExperienceWeaponJavelin, ExperienceWeaponGreatsword, ExperienceWeaponSword, ExperienceWeaponSledgeHammer, ExperienceWeaponLightShield,
                     ExperienceWeaponTwoHandedHammer, ExperienceWeaponHatchet, ExperienceWeaponWarAxe,
                     ExperienceWeaponThrowingKnife, ExperienceWeaponMesser, #'ExperienceWeaponHeavyCrossbow',
                     )
LEADERBOARDS = [
    'MetaAverageDailyPlaytime', 'GlobalXp', 'Playtime', 'DailyPlaytime', 'ExperienceArcher', 'ExperienceFootman',
    'ExperienceVanguard', 'ExperienceKnight', 'ExperienceWeaponMorningStar',
    'ExperienceWeaponHeavyCavalrySword', 'ExperienceWeaponThrowingMallet',
    'ExperienceWeaponDagger', 'ExperienceWeaponMediumShield', 'ExperienceWeaponHeavyShield',
    'ExperienceWeaponWarBow', 'ExperienceWeaponShovel', 'ExperienceWeaponQuarterstaff',
    'ExperienceWeaponRapier', 'ExperienceWeaponWarHammer', 'ExperienceWeaponThrowingAxe',
    'ExperienceWeaponExecutionersAxe', 'ExperienceWeaponCrossbow', 'ExperienceWeaponPoleHammer',
    'ExperienceWeaponAxe', 'ExperienceWeaponHeavyMace', 'ExperienceWeaponBow',
    'ExperienceWeaponKnife', 'ExperienceWeaponPickAxe', 'ExperienceWeaponCudgel',
    'ExperienceWeaponFalchion', 'ExperienceWeaponWarClub', 'ExperienceWeaponSpear',
    'ExperienceWeaponShortSword', 'ExperienceWeaponOneHandedSpear', 'ExperienceWeaponLance',
    'ExperienceWeaponBattleAxe', 'ExperienceWeaponGlaive', 'ExperienceWeaponMace',
    'ExperienceWeaponHalberd', 'ExperienceWeaponHighlandSword', 'ExperienceWeaponPoleAxe',
    'ExperienceWeaponKatars', 'ExperienceWeaponMaul', 'ExperienceWeaponDaneAxe',
    'ExperienceWeaponBastardSword', 'ExperienceWeaponJavelin', 'ExperienceWeaponGreatsword',
    'ExperienceWeaponSword', 'ExperienceWeaponSledgeHammer', 'ExperienceWeaponLightShield',
    'ExperienceWeaponTwoHandedHammer', 'ExperienceWeaponHatchet', 'ExperienceWeaponWarAxe',
    'ExperienceWeaponThrowingKnife', 'ExperienceWeaponMesser', #'ExperienceWeaponHeavyCrossbow',
]


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

def humanize_leaderboard_name(leaderboard_name):
    return re.sub(r'(?<!^)([A-Z])', r' \1', leaderboard_name.replace('ExperienceWeapon', '')).title().lower()

def test(request):
    now = datetime.datetime.now()
    html = "<html><body>It is now %s.</body></html>" % now
    return HttpResponse(html)

def player_search(request):
    search_query = request.GET.get('search_query', '')
    if search_query:
        players = Player.objects.filter(alias_history__icontains=search_query)
        players = [{'playfabid': player.playfabid, 'name': player.most_common_alias()} for player in players]
    else:
        players = []
    context = {
        'players': players,
        'search_query': search_query,
        'leaderboards': {name: humanize_leaderboard_name(name) for name in LEADERBOARDS},
    }
    return render(request, 'leaderboards/player_search.html', context)

def leaderboard_name_to_url(leaderboard_name):
    if leaderboard_name.startswith('ExperienceWeapon'):
        leaderboard_name = leaderboard_name.replace('ExperienceWeapon', '')
    return re.sub(r'(?<!^)([A-Z])', r'-\1', leaderboard_name).lower()

def url_to_leaderboard_name(url):
    formatted_url = url.replace('-', ' ').title().replace(' ', '')
    print(f'Formatted URL: {formatted_url}')  # Debugging line
    if not any(formatted_url.startswith(word) for word in
               ['GlobalXp', 'Playtime', 'DailyPlaytime', 'ExperienceArcher', 'ExperienceFootman', 'ExperienceVanguard',
                'ExperienceKnight']):
        formatted_url = 'ExperienceWeapon' + formatted_url
    return formatted_url


LEADERBOARDS_DICT = {leaderboard_name_to_url(name): name for name in LEADERBOARDS}

def index(request):
    latest_entry = ChivstatsSumstats.objects.latest('serial_date')
    context = {
        'leaderboards': {name: humanize_leaderboard_name(name) for name in LEADERBOARDS},
        'latest_entry': latest_entry,
    }
    return render(request, 'leaderboards/index.html', context)

def leaderboard(request, leaderboard_name):
    leaderboard_name = leaderboard_name.replace(' ', '')  # Remove the space
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
    if leaderboard_name not in LEADERBOARDS:
        raise Http404("Leaderboard does not exist")
    leaderboard_data, page_obj, latest_update = get_leaderboard_data(leaderboard_name, page_number, results_per_page, search_query)
    context = {
        'leaderboard_data': leaderboard_data,
        'page_obj': page_obj,
        'leaderboard_name': humanize_leaderboard_name(leaderboard_name),
        'latest_update': latest_update,
        'leaderboards': {name: humanize_leaderboard_name(name) for name in LEADERBOARDS},
        'search_query': search_query,
    }
    return render(request, 'leaderboards/leaderboard.html', context)

def get_leaderboard_data(leaderboard_name, page_number, results_per_page=50, search_query=''):
    if leaderboard_name not in LEADERBOARDS:
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
    for leaderboard_name in LEADERBOARDS:
        leaderboard_model = globals()[leaderboard_name]
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
        highest_stat_value = DailyPlaytime.objects.filter(
            playfabid=player,
            playfabid__playfabid=playfabid,  # Filter for specific playfabid
            serialnumber__startswith=date_str
        ).aggregate(Max('stat_value'))['stat_value__max']
        if highest_stat_value:
            playtime_entry = DailyPlaytime.objects.filter(
                playfabid=player,
                playfabid__playfabid=playfabid,  # Filter for specific playfabid
                serialnumber__startswith=date_str,
                stat_value=highest_stat_value
            ).first()
            playtime_data.append({
                'date': date.strftime("%B %d, %Y"),
                'playtime': playtime_entry.stat_value,
            })
    print(playtime_data)
    context = {
        'playfabid': playfabid,
        'player': player,
        'aliases': player.aliases(),
        'leaderboard_data': leaderboard_data,
        'latest_serial_numbers': latest_serial_numbers,
        'leaderboards': {name: humanize_leaderboard_name(name) for name in LEADERBOARDS},
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
        'leaderboards': {name: humanize_leaderboard_name(name) for name in LEADERBOARDS},
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



from rest_framework import generics, serializers
from .models import Leaderboard, Player
from .serializers import LeaderboardSerializer

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