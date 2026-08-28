# Management command to process the email queue
# AD-004: Async email sending with queue and retry logic

from django.core.management.base import BaseCommand
from django.utils import timezone
from emails.models import Email, EmailQueue
from emails.utils import EmailSenderService, send_email_sync
import logging

# Set up logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Process the email queue and send pending emails."""
    
    help = 'Process the email queue and send pending emails'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of emails to process (default: 10)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Run in dry-run mode (no actual sending)'
        )
        
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            default=False,
            help='Retry failed emails instead of processing queue'
        )
        
        parser.add_argument(
            '--email-id',
            type=int,
            default=None,
            help='Process only a specific email ID'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution."""
        limit = options['limit']
        dry_run = options['dry_run']
        retry_failed = options['retry_failed']
        email_id = options['email_id']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode - no emails will be sent'))
        
        if retry_failed:
            self.process_retry_failed(dry_run, limit)
        else:
            self.process_queue(dry_run, limit, email_id)
    
    def process_queue(self, dry_run, limit, email_id):
        """Process the email queue."""
        if email_id:
            # Process only specific email
            emails = Email.objects.filter(pk=email_id, status='QUEUED')
        else:
            # Process all queued emails, limited
            emails = Email.objects.filter(status='QUEUED').order_by('created_at')[:limit]
        
        if not emails.exists():
            self.stdout.write(self.style.SUCCESS('No queued emails found to process'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found {emails.count()} queued emails to process'))
        
        processed_count = 0
        success_count = 0
        failed_count = 0
        
        for email in emails:
            try:
                self.stdout.write(f'Processing email {email.id}: {email.subject}')
                
                if dry_run:
                    self.stdout.write(self.style.WARNING(f'  [DRY RUN] Would process email {email.id}'))
                    processed_count += 1
                    continue
                
                # Get SMTP config
                smtp_config = email.smtp_config
                if not smtp_config:
                    # Try to get from mailing lists
                    for mailing_list in email.mailing_lists.all():
                        if mailing_list.smtp_config:
                            smtp_config = mailing_list.smtp_config
                            break
                
                if not smtp_config:
                    self.stdout.write(self.style.ERROR(f'  No SMTP config for email {email.id}'))
                    email.status = 'FAILED'
                    email.error_message = 'No SMTP configuration available'
                    email.save()
                    failed_count += 1
                    continue
                
                # Get recipients
                recipients = email.get_unique_recipient_emails()
                
                if not recipients:
                    self.stdout.write(self.style.ERROR(f'  No recipients for email {email.id}'))
                    email.status = 'FAILED'
                    email.error_message = 'No recipients selected'
                    email.save()
                    failed_count += 1
                    continue
                
                # Send email
                self.stdout.write(f'  Sending to {len(recipients)} recipients...')
                
                results = send_email_sync(email, recipients, smtp_config)
                
                processed_count += 1
                success_count += results['success']
                failed_count += results['failed']
                
                # Update email status
                if results['failed'] == 0:
                    email.status = 'SENT'
                    email.sent_at = timezone.now()
                else:
                    email.status = 'FAILED'
                    email.error_message = "; ".join(results['errors'])
                email.save()
                
                # Create/update queue entries
                for recipient in recipients:
                    if isinstance(recipient, str):
                        to_email = recipient
                        recipient_obj = None
                    else:
                        to_email = recipient.email
                        recipient_obj = recipient
                    
                    status = 'SENT' if results['failed'] == 0 else 'FAILED'
                    error_msg = None if results['failed'] == 0 else results['errors'][0] if results['errors'] else "Unknown error"
                    
                    queue_entry, created = EmailQueue.objects.get_or_create(
                        email=email,
                        to_email=to_email,
                        defaults={
                            'recipient': recipient_obj,
                            'status': status,
                            'error_message': error_msg,
                            'sent_at': timezone.now() if status == 'SENT' else None
                        }
                    )
                    
                    if not created:
                        queue_entry.status = status
                        queue_entry.error_message = error_msg
                        if status == 'SENT':
                            queue_entry.sent_at = timezone.now()
                        queue_entry.save()
                
                if results['failed'] == 0:
                    self.stdout.write(self.style.SUCCESS(f'  Successfully sent email {email.id}'))
                else:
                    self.stdout.write(self.style.ERROR(f'  Failed to send email {email.id}: {results["errors"][0] if results["errors"] else "Unknown error"}'))
                
            except Exception as e:
                logger.error(f'Error processing email {email.id}: {str(e)}')
                self.stdout.write(self.style.ERROR(f'  Exception processing email {email.id}: {str(e)}'))
                
                email.status = 'FAILED'
                email.error_message = str(e)
                email.save()
                failed_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'Processed {processed_count} emails: {success_count} sent, {failed_count} failed'
        ))
    
    def process_retry_failed(self, dry_run, limit):
        """Retry failed emails."""
        # Get failed queue entries that can be retried
        retryable_entries = EmailQueue.objects.filter(
            status='FAILED',
            attempts__lt=2
        ).order_by('created_at')[:limit]
        
        if not retryable_entries.exists():
            self.stdout.write(self.style.SUCCESS('No failed emails to retry'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found {retryable_entries.count()} failed emails to retry'))
        
        retried_count = 0
        failed_count = 0
        
        for entry in retryable_entries:
            try:
                self.stdout.write(f'Retrying queue entry {entry.id} for email {entry.email.id}')
                
                if dry_run:
                    self.stdout.write(self.style.WARNING(f'  [DRY RUN] Would retry queue entry {entry.id}'))
                    retried_count += 1
                    continue
                
                email = entry.email
                smtp_config = email.smtp_config
                
                if not smtp_config:
                    for mailing_list in email.mailing_lists.all():
                        if mailing_list.smtp_config:
                            smtp_config = mailing_list.smtp_config
                            break
                
                if not smtp_config:
                    self.stdout.write(self.style.ERROR(f'  No SMTP config for email {email.id}'))
                    entry.error_message = "No SMTP configuration available"
                    entry.save()
                    failed_count += 1
                    continue
                
                # Reset status for retry
                entry.status = 'PENDING'
                entry.save()
                
                # Send the email
                results = send_email_sync(email, [entry.to_email], smtp_config)
                
                if results['failed'] == 0:
                    entry.mark_as_sent()
                    retried_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  Successfully retried queue entry {entry.id}'))
                else:
                    entry.mark_as_failed(results['errors'][0] if results['errors'] else "Unknown error")
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f'  Failed to retry queue entry {entry.id}: {results["errors"][0] if results["errors"] else "Unknown error"}'))
                
            except Exception as e:
                logger.error(f'Error retrying queue entry {entry.id}: {str(e)}')
                self.stdout.write(self.style.ERROR(f'  Exception retrying queue entry {entry.id}: {str(e)}'))
                
                entry.mark_as_failed(str(e))
                failed_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'Retried {retried_count + failed_count} emails: {retried_count} successful, {failed_count} failed'
        ))
