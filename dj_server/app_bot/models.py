from datetime import datetime

from django.db import models

from dj_server.config import CATEGORY_CHOICES

# Create your models here.

class Admin(models.Model):
    admin_id = models.BigIntegerField()
    is_notification_enabled = models.BooleanField(default=True)

class User(models.Model):
    user_id = models.BigIntegerField()

class Part(models.Model):
    part_id = models.BigAutoField(primary_key=True)
    is_available = models.BooleanField(default=True)
    name = models.CharField(max_length=128)
    category = models.CharField(max_length=8, choices=CATEGORY_CHOICES, default="OTHER")
    description = models.TextField(max_length=256)
    price = models.FloatField(default=0.0)
    available_count = models.PositiveIntegerField(default=0)
    image = models.FileField(
        upload_to="img/parts",
        default="img/static/no_img_part.jpg"
    )
    
class Order(models.Model):
    order_id = models.BigAutoField(primary_key=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    parts = models.JSONField(default=dict)
    cost = models.FloatField(default=0.0)

class ConfirmedOrder(models.Model):
    order_id = models.BigIntegerField(primary_key=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    parts = models.JSONField(default=dict)
    cost = models.FloatField(default=0.0)
    ordered_time = models.DateTimeField()
    is_accepted = models.BooleanField(default=False)
    accepted_time = models.DateTimeField()

class CompletedOrder(models.Model):
    order_id = models.BigIntegerField(primary_key=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    parts = models.JSONField(default=dict)
    cost = models.FloatField(default=0.0)
    ordered_time = models.DateTimeField()
    accepted_time = models.DateTimeField()
    completed_time = models.DateTimeField()