from django.contrib import admin
from retells.admin import custom_admin_site
from .models import ProductDetails
from django.utils.html import format_html

class ProductDetailsAdmin(admin.ModelAdmin):
    list_display = ['id','name', 'email','post_code','product_id', 'product_name','product_color','branding_option', 'quantity', 'delivery_time']
custom_admin_site.register(ProductDetails,ProductDetailsAdmin)