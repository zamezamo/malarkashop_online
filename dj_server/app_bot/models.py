import datetime

from django.db import models

from dj_server.config import CATEGORY_CHOICES, DEFAULT_PART_IMAGE

# Create your models here.

class User(models.Model):
    user_id = models.BigIntegerField(primary_key=True, default=0, verbose_name="ID пользователя в тг")
    username = models.CharField(max_length=64, default="", verbose_name="username пользователя в тг")
    name = models.CharField(max_length=64, default="", verbose_name="имя пользователя")
    phone_number = models.CharField(max_length=9, default="", verbose_name="моб. номер")
    delivery_address = models.CharField(max_length=128, default="", verbose_name="адрес доставки")

    def __str__(self):
        return f"{self.name}, {self.username}, +375{self.phone_number}"

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"


class Admin(models.Model):
    admin_id = models.BigIntegerField(primary_key=True, verbose_name="ID админа в тг")
    admin_name = models.CharField(max_length=64, default="админ", verbose_name="имя")
    is_notification_enabled = models.BooleanField(default=True, verbose_name="уведомления включены?")

    class Meta:
        verbose_name = "админ"
        verbose_name_plural = "админы"


class Part(models.Model):
    part_id = models.BigAutoField(primary_key=True, verbose_name="ID товара")
    is_available = models.BooleanField(default=True, verbose_name="доступен в каталоге?")
    name = models.CharField(max_length=64, default="", verbose_name="имя")
    category = models.CharField(max_length=64, choices=CATEGORY_CHOICES, default="OTHER", verbose_name="категория")
    description = models.TextField(max_length=256, default="", verbose_name="описание")
    price = models.FloatField(default=0.0, verbose_name="цена")
    available_count = models.PositiveIntegerField(default=0, verbose_name="доступное количество")
    image = models.ImageField(
        upload_to="",
        default=f"img/static/{DEFAULT_PART_IMAGE}",
        verbose_name="фото",
        max_length=256
    )

    class Meta:
        verbose_name = "товар"
        verbose_name_plural = "товары"
    

class Order(models.Model):
    order_id = models.BigAutoField(primary_key=True, verbose_name="номер заказа")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="пользователь в тг")
    parts = models.JSONField(default=dict, verbose_name="товары в корзине")
    cost = models.FloatField(default=0.0, verbose_name="стоимость корзины")

    class Meta:
        verbose_name = "заказ в корзине"
        verbose_name_plural = "заказы в корзине"


class ConfirmedOrder(models.Model):
    order_id = models.BigIntegerField(primary_key=True, verbose_name="номер заказа")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="пользователь в тг")
    parts = models.JSONField(default=dict, verbose_name="товары в заказе")
    cost = models.FloatField(default=0.0, verbose_name="стоимость заказа")
    ordered_time = models.DateTimeField(default=datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc), verbose_name="время оформления")
    is_accepted = models.BooleanField(default=False, verbose_name="заказ принят?")
    accepted_time = models.DateTimeField(default=datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc), verbose_name="время принятия")

    class Meta:
        verbose_name = "выполняемый заказ"
        verbose_name_plural = "выполняемые заказы"


class CompletedOrder(models.Model):
    order_id = models.BigIntegerField(primary_key=True, verbose_name="номер заказа")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="пользователь в тг")
    parts = models.JSONField(default=dict, verbose_name="товары в заказе")
    cost = models.FloatField(default=0.0, verbose_name="стоимость заказа")
    ordered_time = models.DateTimeField(default=datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc), verbose_name="время оформления")
    accepted_time = models.DateTimeField(default=datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc), verbose_name="время принятия")
    completed_time = models.DateTimeField(default=datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc), verbose_name="время доставки")

    class Meta:
        verbose_name = "доставленный заказ"
        verbose_name_plural = "доставленные заказы"