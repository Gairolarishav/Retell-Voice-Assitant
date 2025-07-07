from django.shortcuts import render
from .models import ProductDetails
from rest_framework.decorators import api_view
from django.http import JsonResponse
import json
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@require_POST
def product_details(request):
    if request.method == "POST":
        try:
            data = request.POST

            order = ProductDetails.objects.create(
                product_id=data.get("product_id"),
                product_name=data.get("product_name"),
                product_color=data.get("product_color"),
                branding_option=data.get("branding_option"),
                quantity=data.get("quantity"),
                delivery_time=data.get("delivery_time"),
                name=data.get("name"),
                email=data.get("email"),
                post_code=data.get("post_code"),
            )
            return JsonResponse({
                "message": f"Order saved successfully for {data.get("product_name")} — Order ID: {order.id}"
            }, status=201)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)
