from django.urls import path
from . import views
from .views import PlayerListAPIView, LatestLeaderboardListAPIView, LeaderboardListAPIView, get_leaderboard

app_name = 'leaderboards'

urlpatterns = [
    path('', views.index, name='index'),
    path('player_search/', views.player_search, name='player_search'),
    path('top_players/', views.top_players_by_playtime, name='top_players'),
    path('top_gainers/', views.top_gainers_leaderboard, name='top_gainers_leaderboard'),
    path('go_touch_grass/', views.go_touch_grass_leaderboard, name='go_touch_grass_leaderboard'),
    path('player/<str:playfabid>/', views.player_profile, name='player_profile'),
    path('tattle/', views.tattle, name='tattle'),
    path('api/players/', PlayerListAPIView.as_view(), name='player-list-api'),
    path('api/latest-leaderboards/', LatestLeaderboardListAPIView.as_view(), name='latest-leaderboards'),
    path('api/leaderboards/', LeaderboardListAPIView.as_view(), name='leaderboards-api'),
    path('api/get_leaderboard/', views.get_leaderboard, name='get_leaderboard'),
    path('hourly_player_count/', views.get_hourly_player_count, name='hourly_player_count'),
    path('api/hourly-player-count/', views.get_hourly_player_count, name='api_hourly_player_count'),
    path('<str:leaderboard_name>/', views.leaderboard, name='leaderboard'),
]
