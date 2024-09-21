from django.db import models

# Create your models here.

class Admin(models.Model):
    admin_id = models.BigIntegerField()

class User(models.Model):
    user_id = models.BigIntegerField()

class Part(models.Model):
    part_id = models.AutoField(primary_key=True)
    image = models.FileField(upload_to="settings.MEDIA_ROOT/parts", default="default_part.jpg", name="1")
    available_count = models.IntegerField(default=0)
    name = models.CharField(max_length=64)
    description = models.TextField(max_length=256)

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