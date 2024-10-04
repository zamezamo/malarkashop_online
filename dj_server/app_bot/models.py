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
    name = models.CharField(max_length=64)
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default=CATEGORY_CHOICES["OTHER"])
    description = models.TextField(max_length=256)
    available_count = models.IntegerField(default=0)
    image = models.FileField(upload_to="settings.MEDIA_ROOT/img/parts", default="no_img_part.jpg", name=f"part_{name}_{part_id}")

class Order(models.Model):
    order_id = models.BigAutoField(primary_key=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    parts = models.JSONField(default={})
    ordered_time = models.DateTimeField(default=datetime.now())
    is_accepted = models.BooleanField(default=False)
    accepted_time = models.DateTimeField(default=datetime.now())

class CompletedOrder(models.Model):
    order_id = models.BigIntegerField(primary_key=True)
    user_id = models.BigIntegerField()
    parts = models.JSONField(default={})
    ordered_time = models.DateTimeField(default=datetime.now())
    accepted_time = models.DateTimeField(default=datetime.now())
    completed_time = models.DateTimeField(default=datetime.now())