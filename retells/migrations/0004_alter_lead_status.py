# Generated by Django 5.2.1 on 2025-06-02 08:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('retells', '0003_callhistory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lead',
            name='status',
            field=models.CharField(choices=[('NEW', 'New'), ('CONTACTED', 'Contacted')], default='NEW', max_length=20),
        ),
    ]
