from django.contrib import admin

from .forms import MultilingualBarFormAllFields
from .models import Bar


class BarAdmin(admin.ModelAdmin):
    form = MultilingualBarFormAllFields
    list_display = ('name', 'price', 'quantity', 'description',)
    list_filter = ('name',)
    search_fields = ('name', 'description',)


admin.site.register(Bar, BarAdmin)
