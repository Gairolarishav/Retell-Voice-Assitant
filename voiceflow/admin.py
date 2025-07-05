from django.contrib import admin
from .models import Dummy
from retells.admin import custom_admin_site  # Import the shared instance

custom_admin_site.register(Dummy)