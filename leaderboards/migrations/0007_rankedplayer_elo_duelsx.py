# Generated by Django 4.2.2 on 2024-01-05 05:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaderboards', '0006_rename_recent_alias_player_alias_recent'),
    ]

    operations = [
        migrations.AddField(
            model_name='rankedplayer',
            name='elo_duelsx',
            field=models.BigIntegerField(default=1500),
        ),
    ]