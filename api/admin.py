from django.contrib import admin
from .models import Transmission

@admin.register(Transmission)
class TransmissionAdmin(admin.ModelAdmin):
    list_display = ('id','timestamp','role','device','status','msg_id')
    list_filter = ('role','status')
    search_fields = ('message','device')
    ordering = ('-timestamp',)
