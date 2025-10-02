from django.contrib import admin
from .models import User, Tool, Rental, Payment

admin.site.register(User)
admin.site.register(Tool)
admin.site.register(Rental)
admin.site.register(Payment)

# Register your models here.