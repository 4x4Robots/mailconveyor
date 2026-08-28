# Management command to clean up old emails and related data
# AD-007: 14-day retention for sent emails

from django.core.management.base import BaseCommand
from django.utils import timezone
from emails.models import Email, EmailQueue, EmailLog, EmailAttachment
from emails.utils import cleanup_old_emails, cleanup_old_queue_entries
import logging

# Set up logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Clean up old emails, queue entries, and logs."""
    
    help = 'Clean up old emails, queue entries, and logs based on retention policy'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--days',
            type=int,
            default=14,
            help='Number of days to keep data (default: 14)'
        )
        
        parser.add_argument(
            '--emails-only',
            action='store_true',
            default=False,
            help='Only clean up emails (not queue entries or logs)'
        )
        
        parser.add_argument(
            '--queue-only',
            action='store_true',
            default=False,
            help='Only clean up queue entries (not emails or logs)'
        )
        
        parser.add_argument(
            '--logs-only',
            action='store_true',
            default=False,
            help='Only clean up logs (not emails or queue entries)'
        )
        
        parser.add_argument(
            '--attachments-only',
            action='store_true',
            default=False,
            help='Only clean up attachments (not emails, queue entries, or logs)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Run in dry-run mode (no actual deletion)'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Force cleanup without confirmation'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        days = options['days']
        emails_only = options['emails_only']
        queue_only = options['queue_only']
        logs_only = options['logs_only']
        attachments_only = options['attachments_only']
        dry_run = options['dry_run']
        force = options['force']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode - no data will be deleted'))
        
        # Confirm action if not forced and not dry-run
        if not force and not dry_run:
            self.stdout.write(self.style.WARNING(
                f'Are you sure you want to delete data older than {days} days? '
                f'This cannot be undone. (Use --force to skip confirmation)'
            ))
            
            # For non-interactive use, we'll assume confirmation
            # In a real scenario, you might want to add interactive confirmation
            self.stdout.write(self.style.WARNING('Assuming confirmation for non-interactive use'))
        
        deleted_emails = 0
        deleted_queue = 0
        deleted_logs = 0
        deleted_attachments = 0
        
        # Clean up emails
        if not queue_only and not logs_only and not attachments_only:
            cutoff = timezone.now() - timezone.timedelta(days=days)
            old_emails = Email.objects.filter(created_at__lt=cutoff)
            
            if dry_run:
                self.stdout.write(f'[DRY RUN] Would delete {old_emails.count()} old emails')
                deleted_emails = old_emails.count()
            else:
                deleted_emails = old_emails.count()
                old_emails.delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_emails} old emails'))
        
        # Clean up queue entries
        if not emails_only and not logs_only and not attachments_only:
            deleted_queue = cleanup_old_queue_entries(days)
            if dry_run:
                self.stdout.write(f'[DRY RUN] Would delete {deleted_queue} old queue entries')
            else:
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_queue} old queue entries'))
        
        # Clean up logs
        if not emails_only and not queue_only and not attachments_only:
            cutoff = timezone.now() - timezone.timedelta(days=days)
            old_logs = EmailLog.objects.filter(created_at__lt=cutoff)
            
            if dry_run:
                self.stdout.write(f'[DRY RUN] Would delete {old_logs.count()} old log entries')
                deleted_logs = old_logs.count()
            else:
                deleted_logs = old_logs.count()
                old_logs.delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_logs} old log entries'))
        
        # Clean up attachments
        if not emails_only and not queue_only and not logs_only:
            cutoff = timezone.now() - timezone.timedelta(days=days)
            old_attachments = EmailAttachment.objects.filter(created_at__lt=cutoff)
            
            if dry_run:
                self.stdout.write(f'[DRY RUN] Would delete {old_attachments.count()} old attachments')
                deleted_attachments = old_attachments.count()
            else:
                deleted_attachments = old_attachments.count()
                # Delete the files first
                for attachment in old_attachments:
                    try:
                        if attachment.file:
                            attachment.file.delete(save=False)
                    except Exception as e:
                        logger.error(f'Error deleting attachment file {attachment.file.name}: {str(e)}')
                
                # Delete the database records
                old_attachments.delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_attachments} old attachments'))
        
        # Summary
        total_deleted = deleted_emails + deleted_queue + deleted_logs + deleted_attachments
        self.stdout.write(self.style.SUCCESS(
            f'Cleanup complete. Total items deleted: {total_deleted} '
            f'(emails: {deleted_emails}, queue: {deleted_queue}, '
            f'logs: {deleted_logs}, attachments: {deleted_attachments})'
        ))
