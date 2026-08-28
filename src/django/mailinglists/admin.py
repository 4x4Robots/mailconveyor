# MailingLists app admin configuration

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from .models import MailingList, SmtpConfig


class SmtpConfigInline(admin.StackedInline):
    """Inline admin for SMTP configuration within MailingList admin."""
    model = SmtpConfig
    can_delete = True
    extra = 0
    max_num = 1
    exclude = ('_password',)  # Exclude the encrypted password field


@admin.register(MailingList)
class MailingListAdmin(GuardedModelAdmin):
    """Admin configuration for MailingList model."""
    
    list_display = ('name', 'description_short', 'created_by', 'created_at', 'updated_at', 'access_count')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'description', 'created_by__username')
    ordering = ('name',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'created_by')
        }),
        ('Access Control', {
            'fields': ('users_with_access',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('users_with_access',)
    
    inlines = [SmtpConfigInline]
    
    def description_short(self, obj):
        """Short description for list display."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return ''
    
    description_short.short_description = 'Description'
    
    def access_count(self, obj):
        """Number of users with access."""
        return obj.users_with_access.count()
    
    access_count.short_description = 'Users with Access'
    
    def save_model(self, request, obj, form, change):
        """Set created_by to current user if not set."""
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SmtpConfig)
class SmtpConfigAdmin(admin.ModelAdmin):
    """Admin configuration for SmtpConfig model."""
    
    list_display = ('mailing_list', 'host', 'port', 'username', 'use_tls', 'use_ssl', 'default_from_email')
    list_filter = ('use_tls', 'use_ssl')
    search_fields = ('mailing_list__name', 'host', 'username', 'default_from_email')
    ordering = ('mailing_list__name',)
    
    fieldsets = (
        (None, {
            'fields': ('mailing_list',)
        }),
        ('Connection Settings', {
            'fields': ('host', 'port', 'use_tls', 'use_ssl')
        }),
        ('Authentication', {
            'fields': ('username', 'password_display')
        }),
        ('Email Settings', {
            'fields': ('default_from_email',)
        }),
    )
    
    readonly_fields = ('password_display',)
    exclude = ('_password',)  # Exclude the encrypted password field
    
    def password_display(self, obj):
        """Display masked password."""
        if obj._password:
            return '**********'
        return 'Not set'
    
    password_display.short_description = 'Password'