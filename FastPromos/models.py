from django.db import models

# Create your models here.
class ProductDetails(models.Model):
    product_id = models.CharField(max_length=255)
    product_name = models.CharField(max_length=255)
    product_color = models.CharField(max_length=100)
    branding_option = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    delivery_time = models.CharField(max_length=100)

    name = models.CharField(max_length=100)
    email = models.EmailField()
    post_code = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product Details"
        verbose_name_plural = "Product Details"

    def __str__(self):
        return f"{self.name} - {self.product_name}"
