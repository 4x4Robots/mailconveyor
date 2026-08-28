# Recipients app admin configuration

from django.contrib import admin
from .models import Recipient, RecipientImportLog


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    """Admin configuration for Recipient model."""
    
    list_display = ('get_full_name', 'email', 'created_at', 'created_by', 'mailing_list_count')
    list_filter = ('created_at', 'created_by')
    search_fields = ('first_name', 'last_name', 'email')
    filter_horizontal = ('mailing_lists',)
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    get_full_name.short_description = 'Full Name'
    
    def mailing_list_count(self, obj):
        return obj.mailing_lists.count()
    mailing_list_count.short_description = 'Mailing Lists'


@admin.register(RecipientImportLog)
class RecipientImportLogAdmin(admin.ModelAdmin):
    """Admin configuration for RecipientImportLog model."""
    
    list_display = ('file_name', 'uploaded_by', 'status', 'total_records', 
                   'successful_records', 'failed_records', 'created_at', 'completed_at')
    list_filter = ('status', 'created_at', 'uploaded_by')
    search_fields = ('file_name', 'error_message')
    readonly_fields = ('created_at', 'completed_at')
