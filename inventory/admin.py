from django.contrib import admin
from .models import User, Tool, Rental, Payment, Customer, Sale

admin.site.register(User)
admin.site.register(Tool)
admin.site.register(Rental)
admin.site.register(Payment)
admin.site.register(Customer)
admin.site.register(Sale)