# Generated by Django 5.2 on 2025-04-22 15:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='social_security_number',
        ),
        migrations.AddField(
            model_name='user',
            name='next_of_kin',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='occupation',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
