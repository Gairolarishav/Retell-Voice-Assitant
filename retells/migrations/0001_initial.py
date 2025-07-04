# Generated by Django 5.1.3 on 2025-05-31 06:39

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Lead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100, null=True)),
                ('phone_number', models.CharField(max_length=20, unique=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('property_interest', models.CharField(blank=True, max_length=255, null=True)),
                ('source', models.CharField(blank=True, max_length=100, null=True)),
                ('status', models.CharField(choices=[('NEW', 'New'), ('CONTACTED', 'Contacted'), ('IN_PROGRESS', 'In Progress'), ('QUALIFIED', 'Qualified'), ('UNQUALIFIED', 'Unqualified'), ('CLOSED', 'Closed')], default='NEW', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
