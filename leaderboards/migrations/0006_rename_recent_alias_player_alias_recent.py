# Generated by Django 4.2.2 on 2024-01-02 16:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('leaderboards', '0005_player_recent_alias'),
    ]

    operations = [
        migrations.RenameField(
            model_name='player',
            old_name='recent_alias',
            new_name='alias_recent',
        ),
    ]
