# Generated by Django 5.2.1 on 2025-06-03 06:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retells', '0006_batchcall_uuid_alter_batchcall_batch_call_id_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='callhistory',
            name='retell_call_id',
        ),
        migrations.AddField(
            model_name='callhistory',
            name='agent_id',
            field=models.CharField(blank=True, help_text='Retell Agent ID', max_length=255),
        ),
    ]
