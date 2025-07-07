from django.urls import path
from . import views

urlpatterns = [
    path('product-details/', views.product_details, name='product_details'),
]