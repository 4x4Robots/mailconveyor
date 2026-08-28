# Emails app admin configuration

from django.contrib import admin
from .models import Email, EmailTemplate, EmailAttachment, EmailQueue, EmailLog


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for EmailTemplate."""
    
    list_display = ['name', 'subject', 'is_html', 'mailing_list', 'created_by', 'created_at', 'updated_at']
    list_filter = ['is_html', 'mailing_list', 'created_by']
    search_fields = ['name', 'subject', 'body']
    raw_id_fields = ['mailing_list', 'created_by']
    
    fieldsets = [
        (None, {
            'fields': ['name', 'subject', 'body', 'is_html']
        }),
        ('Classification', {
            'fields': ['mailing_list', 'created_by']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at']
        }),
    ]
    
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    """Admin configuration for Email."""
    
    list_display = ['subject', 'from_email', 'status', 'created_by', 'created_at', 'sent_at']
    list_filter = ['status', 'created_by', 'created_at', 'sent_at']
    search_fields = ['subject', 'body', 'from_email', 'error_message']
    raw_id_fields = ['created_by', 'recipients', 'mailing_lists', 'smtp_config']
    
    fieldsets = [
        (None, {
            'fields': ['subject', 'body', 'is_html', 'from_email']
        }),
        ('Status', {
            'fields': ['status', 'sent_at', 'error_message', 'attempts']
        }),
        ('Recipients', {
            'fields': ['recipients', 'mailing_lists']
        }),
        ('Configuration', {
            'fields': ['smtp_config', 'created_by']
        }),
        ('Bounce Handling', {
            'fields': ['bounce_message', 'log_file']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at']
        }),
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'sent_at', 'attempts']
    
    # Custom actions
    actions = ['mark_as_sent', 'mark_as_failed', 'retry_failed']
    
    def mark_as_sent(self, request, queryset):
        """Mark selected emails as sent."""
        updated = queryset.update(status='SENT', sent_at=timezone.now())
        self.message_user(request, f"Marked {updated} emails as sent.")
    
    def mark_as_failed(self, request, queryset):
        """Mark selected emails as failed."""
        updated = queryset.update(status='FAILED')
        self.message_user(request, f"Marked {updated} emails as failed.")
    
    def retry_failed(self, request, queryset):
        """Retry failed emails."""
        from .utils import retry_failed_sync
        
        failed_emails = queryset.filter(status='FAILED')
        results = retry_failed_sync()
        
        self.message_user(request, 
            f"Retried {results['retried'] + results['failed']} emails: "
            f"{results['retried']} successful, {results['failed']} failed")


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    """Admin configuration for EmailAttachment."""
    
    list_display = ['filename', 'email', 'created_at']
    list_filter = ['created_at']
    search_fields = ['filename']
    raw_id_fields = ['email']
    
    fieldsets = [
        (None, {
            'fields': ['email', 'file', 'filename']
        }),
        ('Timestamps', {
            'fields': ['created_at']
        }),
    ]
    
    readonly_fields = ['created_at']


@admin.register(EmailQueue)
class EmailQueueAdmin(admin.ModelAdmin):
    """Admin configuration for EmailQueue."""
    
    list_display = ['email', 'to_email', 'status', 'attempts', 'created_at', 'sent_at']
    list_filter = ['status', 'created_at', 'sent_at']
    search_fields = ['to_email', 'error_message']
    raw_id_fields = ['email', 'recipient']
    
    fieldsets = [
        (None, {
            'fields': ['email', 'recipient', 'to_email']
        }),
        ('Status', {
            'fields': ['status', 'attempts', 'sent_at', 'error_message']
        }),
        ('Priority', {
            'fields': ['priority']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at']
        }),
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'sent_at']
    
    # Custom actions
    actions = ['mark_as_sent', 'mark_as_failed', 'retry_selected']
    
    def mark_as_sent(self, request, queryset):
        """Mark selected queue entries as sent."""
        from django.utils import timezone
        updated = queryset.update(status='SENT', sent_at=timezone.now())
        self.message_user(request, f"Marked {updated} queue entries as sent.")
    
    def mark_as_failed(self, request, queryset):
        """Mark selected queue entries as failed."""
        updated = queryset.update(status='FAILED')
        self.message_user(request, f"Marked {updated} queue entries as failed.")
    
    def retry_selected(self, request, queryset):
        """Retry selected failed queue entries."""
        retryable = queryset.filter(status='FAILED', attempts__lt=2)
        updated = retryable.update(status='PENDING')
        self.message_user(request, f"Marked {updated} queue entries for retry.")


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    """Admin configuration for EmailLog."""
    
    list_display = ['email', 'queue_entry', 'log_level', 'operation', 'created_at']
    list_filter = ['log_level', 'operation', 'created_at']
    search_fields = ['message', 'details']
    raw_id_fields = ['email', 'queue_entry']
    
    fieldsets = [
        (None, {
            'fields': ['email', 'queue_entry']
        }),
        ('Log Details', {
            'fields': ['log_level', 'operation', 'message', 'details']
        }),
        ('Timestamps', {
            'fields': ['created_at']
        }),
    ]
    
    readonly_fields = ['created_at']
    
    # Limit the number of logs shown by default
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('-created_at')[:1000]
    
    # Custom actions
    actions = ['clear_old_logs']
    
    def clear_old_logs(self, request, queryset):
        """Clear old log entries."""
        from django.utils import timezone
        
        # Delete logs older than 30 days
        cutoff = timezone.now() - timezone.timedelta(days=30)
        deleted_count, _ = queryset.filter(created_at__lt=cutoff).delete()
        
        self.message_user(request, f"Deleted {deleted_count} old log entries.")
