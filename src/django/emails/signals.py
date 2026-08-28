# Emails app signals
# AD-004: Async email sending with queue and retry logic
# AD-007: 14-day retention for sent emails

from django.db.models.signals import post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Email, EmailQueue, EmailAttachment
import logging

# Set up logging
logger = logging.getLogger(__name__)


@receiver(post_save, sender=Email)
def log_email_creation(sender, instance, created, **kwargs):
    """Log when an email is created or updated."""
    if created:
        logger.info(f"Email {instance.id} created: {instance.subject} by {instance.created_by}")
    else:
        logger.info(f"Email {instance.id} updated: {instance.subject} - status changed to {instance.status}")


@receiver(post_save, sender=EmailQueue)
def log_queue_entry_creation(sender, instance, created, **kwargs):
    """Log when a queue entry is created or updated."""
    if created:
        logger.info(f"Queue entry {instance.id} created for email {instance.email.id} -> {instance.to_email}")
    else:
        logger.info(f"Queue entry {instance.id} updated: status changed to {instance.status}")


@receiver(pre_delete, sender=Email)
def log_email_deletion(sender, instance, **kwargs):
    """Log when an email is about to be deleted."""
    logger.info(f"Email {instance.id} is being deleted: {instance.subject}")


@receiver(post_delete, sender=Email)
def cleanup_email_related_data(sender, instance, **kwargs):
    """Clean up related data when an email is deleted."""
    # Delete queue entries for this email
    queue_entries = EmailQueue.objects.filter(email=instance)
    queue_count = queue_entries.count()
    queue_entries.delete()
    
    if queue_count > 0:
        logger.info(f"Deleted {queue_count} queue entries for email {instance.id}")
    
    # Note: Attachments are deleted via CASCADE, so no need to handle them here


@receiver(pre_delete, sender=EmailAttachment)
def log_attachment_deletion(sender, instance, **kwargs):
    """Log when an attachment is about to be deleted."""
    logger.info(f"Attachment {instance.id} is being deleted: {instance.filename}")


@receiver(post_delete, sender=EmailAttachment)
def cleanup_attachment_file(sender, instance, **kwargs):
    """Clean up the actual file when an attachment is deleted."""
    try:
        if instance.file:
            instance.file.delete(save=False)
            logger.info(f"Deleted attachment file: {instance.file.name}")
    except Exception as e:
        logger.error(f"Error deleting attachment file {instance.file.name}: {str(e)}")


# Signal to handle email status changes
@receiver(post_save, sender=Email)
def handle_email_status_change(sender, instance, **kwargs):
    """Handle actions when email status changes."""
    # If email is marked as SENT, update all related queue entries
    if instance.status == 'SENT':
        EmailQueue.objects.filter(
            email=instance,
            status__in=['PENDING', 'SENDING', 'RETRYING']
        ).update(status='SENT', sent_at=timezone.now())
        
        logger.info(f"Updated queue entries to SENT for email {instance.id}")
    
    # If email is marked as FAILED, update all related queue entries
    elif instance.status == 'FAILED':
        EmailQueue.objects.filter(
            email=instance,
            status__in=['PENDING', 'SENDING', 'RETRYING']
        ).update(status='FAILED', error_message=instance.error_message)
        
        logger.info(f"Updated queue entries to FAILED for email {instance.id}")


# Signal to handle queue entry status changes
@receiver(post_save, sender=EmailQueue)
def handle_queue_status_change(sender, instance, **kwargs):
    """Handle actions when queue entry status changes."""
    # Update parent email status based on queue entries
    if instance.email:
        email = instance.email
        
        # Count statuses for this email's queue entries
        queue_entries = EmailQueue.objects.filter(email=email)
        total_entries = queue_entries.count()
        
        if total_entries == 0:
            return
        
        sent_count = queue_entries.filter(status='SENT').count()
        failed_count = queue_entries.filter(status='FAILED').count()
        pending_count = queue_entries.filter(status='PENDING').count()
        sending_count = queue_entries.filter(status='SENDING').count()
        retrying_count = queue_entries.filter(status='RETRYING').count()
        
        # Update email status based on queue entries
        if sent_count == total_entries:
            # All entries are sent
            if email.status != 'SENT':
                email.status = 'SENT'
                email.sent_at = timezone.now()
                email.save()
                logger.info(f"Email {email.id} status updated to SENT (all queue entries sent)")
        elif failed_count == total_entries:
            # All entries failed
            if email.status != 'FAILED':
                email.status = 'FAILED'
                email.save()
                logger.info(f"Email {email.id} status updated to FAILED (all queue entries failed)")
        elif pending_count > 0 or sending_count > 0 or retrying_count > 0:
            # Some entries are still pending/sending/retrying
            if email.status not in ['QUEUED', 'SENDING', 'RETRYING']:
                email.status = 'QUEUED'
                email.save()
                logger.info(f"Email {email.id} status updated to QUEUED (some queue entries pending)")
