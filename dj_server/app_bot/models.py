from django.db import models

from dj_server.config import CATEGORY_CHOICES

# Create your models here.

class Admin(models.Model):
    admin_id = models.BigIntegerField()
    is_notification_enabled = models.BooleanField()

class User(models.Model):
    user_id = models.BigIntegerField()

class Part(models.Model):
    part_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=64)
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES)
    description = models.TextField(max_length=256)
    image = models.FileField(upload_to="settings.MEDIA_ROOT/parts", default="default_part.jpg", name="CHAAANGEEE IT")
    available_count = models.IntegerField(default=0)

class Order(models.Model):
    order_id = models.BigIntegerField(primary_key=True)
    part_id = models.ForeignKey(Part, on_delete=models.CASCADE)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    ordered_time = models.DateTimeField()
    is_accepted = models.BooleanField()
    accepted_time = models.DateTimeField()

class CompletedOrder(models.Model):
    order_id = models.BigIntegerField(primary_key=True)
    part_id = models.ForeignKey(Part, on_delete=models.CASCADE)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    ordered_time = models.DateTimeField()
    accepted_time = models.DateTimeField()
    completed_time = models.DateTimeField()