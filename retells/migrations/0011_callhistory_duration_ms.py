# Generated by Django 5.2.1 on 2025-06-04 05:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retells', '0010_remove_callhistory_batch_call_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='callhistory',
            name='duration_ms',
            field=models.PositiveBigIntegerField(blank=True, help_text='Call duration in milliseconds', null=True),
        ),
    ]
