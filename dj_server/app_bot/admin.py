from django.contrib import admin
from .models import (
    Admin, User, Part, Order, CompletedOrder
)

# Register your models here.

admin.site.register(Admin)
admin.site.register(User)
admin.site.register(Part)
admin.site.register(Order)
admin.site.register(CompletedOrder)