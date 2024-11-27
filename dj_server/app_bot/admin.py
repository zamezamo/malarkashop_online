from django.contrib import admin
from .models import (
    Admin, User, Part, Order, ConfirmedOrder, CompletedOrder
)

# Register your models here.

class AdminArticle(admin.ModelAdmin):
    list_display = ['admin_id', 'is_notification_enabled']


class UserArticle(admin.ModelAdmin):
    list_display = ['user_id', 'username', 'name', 'phone_number', 'delivery_address']

    search_fields = ['username', 'name', 'phone_number', 'delivery_address']


class PartArticle(admin.ModelAdmin):
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