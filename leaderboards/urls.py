from django.urls import path
from . import views
from .views import PlayerListAPIView, LatestLeaderboardListAPIView, LeaderboardListAPIView, get_leaderboard

app_name = 'leaderboards'

urlpatterns = [
    path('', views.index, name='index'),
    path('player_search/', views.player_search, name='player_search'),
    path('ranked_combat/', views.ranked_combat_leaderboard, name='ranked_combat_leaderboard'),
    path('ranked_matches/', views.ranked_matches, name='ranked_matches'),
    path('about_elo/', views.about_elo, name='about_elo'),
    path('meta_sumstats/', views.get_meta_sumstats, name='meta_sumstats'),
    path('top_players/', views.top_players_by_playtime, name='top_players'),
    path('player_progress/', views.player_progress_over_time, name='player_progress'),
    path('peasant-caps/', views.peasant_caps_leaderboard, name='peasant_caps_leaderboard'),
    path('wealth/', views.wealth_leaderboard, name='wealth_leaderboard'),
    path('top_gainers/', views.top_gainers_leaderboard, name='top_gainers_leaderboard'),
    path('merged_leaderboard_view/', views.merged_leaderboard_view, name='merged_leaderboard_view'),
    path('show_games/', views.show_games, name='show_games'),
    path('go_touch_grass/', views.go_touch_grass_leaderboard, name='go_touch_grass_leaderboard'),
    path('player/<str:playfabid>/', views.player_profile, name='player_profile'),
    path('tattle/', views.tattle, name='tattle'),
    path('api/players/', PlayerListAPIView.as_view(), name='player-list-api'),
    path('api/latest-leaderboards/', LatestLeaderboardListAPIView.as_view(), name='latest-leaderboards'),
    path('api/leaderboards/', LeaderboardListAPIView.as_view(), name='leaderboards-api'),
    path('api/get_leaderboard/', views.get_leaderboard, name='get_leaderboard'),
    path('hourly_player_count/', views.get_hourly_player_count, name='hourly_player_count'),
    path('api/hourly-player-count/', views.get_hourly_player_count, name='api_hourly_player_count'),
    path('daily_unique_accounts/', views.get_daily_unique_accounts, name='daily_unique_accounts'),
    path('api/daily-unique-accounts/', views.get_daily_unique_accounts, name='api_daily_unique_accounts'),
    path('<str:leaderboard_name>/', views.leaderboard, name='leaderboard'),
]
