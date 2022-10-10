from django.contrib import admin

from tests.app.models import AppSession, Message


@admin.register(AppSession)
class AppSessionAdmin(admin.ModelAdmin):
    autocomplete_fields = 'user',


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    pass
