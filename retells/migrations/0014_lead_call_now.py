# Generated by Django 5.2.1 on 2025-06-05 05:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retells', '0013_remove_lead_agent_lead_agent_id_lead_agent_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='call_now',
            field=models.BooleanField(default=False, help_text='Check this to initiate the call immediately.'),
        ),
    ]
