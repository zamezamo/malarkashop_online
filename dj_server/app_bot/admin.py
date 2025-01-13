import datetime
import shutil
from PIL import Image

from dj_server.config import DEFAULT_PART_IMAGE
from dj_server.settings import MEDIA_ROOT

from django.contrib import admin
from .models import (
    Admin, User, Part, Order, ConfirmedOrder, CompletedOrder
)

# Register your models here.

class AdminArticle(admin.ModelAdmin):
    list_display = ['admin_id', 'admin_name', 'is_notification_enabled']


class UserArticle(admin.ModelAdmin):
    list_display = ['user_id', 'username', 'name', 'phone_number', 'delivery_address']

    search_fields = ['username', 'name', 'phone_number', 'delivery_address']


class PartArticle(admin.ModelAdmin):

    def save_model(self, request, obj, form, change):
        load_name = obj.image.name
        file = load_name.rsplit("/", 1)[-1]
        if file != DEFAULT_PART_IMAGE:
            fileext = file.split(".")[-1].lower()
            destination = f"img/parts/{datetime.datetime.now().strftime('%Y_%m_%d')}/part_{obj.category}_{obj.name}.{fileext}"
            if (change) and ("/" in obj.image.name) and (file != f"part_{obj.category}_{obj.name}.{fileext}"):
                shutil.copy(obj.image.path.replace("\\", "/"), MEDIA_ROOT.replace("\\", "/") + "/" + destination)
            obj.image.name = destination
        super().save_model(request, obj, form, change)
        if (file != DEFAULT_PART_IMAGE) and ("/" not in load_name):
            img = Image.open(obj.image.path)
            img = img.resize((1920, 1080))
            img.save(obj.image.path, quality=95)

    list_display = ['part_id', 'is_available', 'name', 'category', 'price', 'available_count']

    list_filter = ['category', 'is_available']

    search_fields = ['part_id', 'name']
    

class OrderArticle(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'cost']

    search_fields = ['order_id']


class ConfirmedOrderArticle(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'cost', 'ordered_time', 'is_accepted', 'accepted_time']

    list_filter = ['ordered_time', 'is_accepted', 'accepted_time']

    search_fields = ['order_id', 'ordered_time', 'accepted_time']


class CompletedOrderArticle(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'cost', 'completed_time']

    list_filter = ['completed_time']

    search_fields = ['order_id', 'completed_time']


admin.site.register(Admin, AdminArticle)
admin.site.register(User, UserArticle)
admin.site.register(Part, PartArticle)
admin.site.register(Order, OrderArticle)
admin.site.register(ConfirmedOrder, ConfirmedOrderArticle)
admin.site.register(CompletedOrder, CompletedOrderArticle)