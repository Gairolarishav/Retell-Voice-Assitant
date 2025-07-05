from django.db import models

# Create your models here.
class Dummy(models.Model):
    class Meta:
        verbose_name = "Custom Pages"
        verbose_name_plural = "Custom Pages"

    def __str__(self):
        return "Placeholder"
