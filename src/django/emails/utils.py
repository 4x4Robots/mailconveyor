# Emails app utilities
# AD-004: Async email sending with queue and retry logic
# AD-009: Rate limiting and bounce logging

import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from django.utils import timezone
from .models import Email, EmailQueue, EmailLog
from mailinglists.models import SmtpConfig, EncryptionUtils
from recipients.models import Recipient
from django.contrib.auth.models import User

# Set up logging
logger = logging.getLogger(__name__)


class AsyncSmtpEmailSender:
    """
    Asynchronous SMTP email sender.
    
    Handles async connection, authentication, and sending of emails
    using the configured SMTP settings from SmtpConfig.
    Implements retry logic and comprehensive logging.
    """
    
    def __init__(self, smtp_config):
        """
        Initialize with SMTP configuration.
        
        Args:
            smtp_config: SmtpConfig instance with SMTP settings
        """
        self.smtp_config = smtp_config
        self.connection = None
        self.error_message = None
        self.log_entries = []
    
    def _get_decrypted_password(self):
        """Get the decrypted SMTP password."""
        if self.smtp_config._password:
            return EncryptionUtils.decrypt(self.smtp_config._password)
        return None
    
    async def connect_async(self):
        """
        Establish async connection to SMTP server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            host = self.smtp_config.host
            port = self.smtp_config.port
            
            # For async SMTP, we'll use aiosmtplib if available
            # For now, we'll use a thread pool executor to run sync smtplib
            # This is a pragmatic approach that works with existing code
            
            # Create connection in a thread
            loop = asyncio.get_event_loop()
            
            def create_connection():
                try:
                    if self.smtp_config.use_ssl:
                        conn = smtplib.SMTP_SSL(host, port)
                    else:
                        conn = smtplib.SMTP(host, port)
                    
                    if self.smtp_config.use_tls and not self.smtp_config.use_ssl:
                        conn.starttls()
                    
                    username = self.smtp_config.username
                    password = self._get_decrypted_password()
                    
                    if username and password:
                        conn.login(username, password)
                    
                    return conn
                except Exception as e:
                    self.error_message = str(e)
                    return None
            
            self.connection = await loop.run_in_executor(None, create_connection)
            
            if self.connection:
                EmailLog.log_operation(
                    operation='CONNECT',
                    log_level='INFO',
                    message=f"Successfully connected to SMTP server: {host}:{port}"
                )
                return True
            else:
                EmailLog.log_operation(
                    operation='CONNECT',
                    log_level='ERROR',
                    message=f"Failed to connect to SMTP server: {host}:{port}. Error: {self.error_message}"
                )
                return False
                
        except Exception as e:
            self.error_message = str(e)
            EmailLog.log_operation(
                operation='CONNECT',
                log_level='ERROR',
                message=f"Exception connecting to SMTP server: {self.error_message}"
            )
            return False
    
    async def send_email_async(self, from_email, to_email, subject, body, is_html=False, attachments=None):
        """
        Send an email asynchronously using the configured SMTP server.
        
        Args:
            from_email: Sender email address
            to_email: Recipient email address
            subject: Email subject
            body: Email body content
            is_html: Whether the body is HTML (default: False)
            attachments: List of file paths to attach (optional)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.connection:
            if not await self.connect_async():
                return False, f"Failed to connect to SMTP server: {self.error_message}"
        
        try:
            # Create message in a thread
            loop = asyncio.get_event_loop()
            
            def create_message():
                if is_html:
                    msg = MIMEMultipart('alternative')
                    msg.attach(MIMEText(body, 'html'))
                else:
                    msg = MIMEText(body, 'plain')
                
                msg['Subject'] = subject
                msg['From'] = from_email
                msg['To'] = to_email
                
                # Add attachments if provided
                if attachments:
                    for file_path in attachments:
                        try:
                            with open(file_path, 'rb') as f:
                                part = MIMEBase('application', 'octet-stream')
                                part.set_payload(f.read())
                                encoders.encode_base64(part)
                                part.add_header('Content-Disposition', f'attachment; filename="{file_path.split("/")[-1]}"')
                                msg.attach(part)
                        except Exception as e:
                            logger.error(f"Failed to attach file {file_path}: {e}")
                
                return msg
            
            msg = await loop.run_in_executor(None, create_message)
            
            # Send email in a thread
            def send_message():
                try:
                    self.connection.sendmail(from_email, [to_email], msg.as_string())
                    return True, "Email sent successfully!"
                except Exception as e:
                    return False, f"Failed to send email: {str(e)}"
            
            success, message = await loop.run_in_executor(None, send_message)
            
            if success:
                EmailLog.log_operation(
                    operation='SEND',
                    log_level='INFO',
                    message=f"Email sent: {subject} from {from_email} to {to_email}"
                )
            else:
                EmailLog.log_operation(
                    operation='SEND',
                    log_level='ERROR',
                    message=f"Email send failed: {subject} from {from_email} to {to_email}. Error: {message}"
                )
            
            return success, message
            
        except Exception as e:
            error_msg = str(e)
            EmailLog.log_operation(
                operation='SEND',
                log_level='ERROR',
                message=f"Exception sending email: {error_msg}"
            )
            return False, f"Failed to send email: {error_msg}"
        
        finally:
            # Don't close connection here - let the caller manage it for bulk sends
            pass
    
    async def close_async(self):
        """Close the SMTP connection asynchronously."""
        if self.connection:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.connection.quit)
                EmailLog.log_operation(
                    operation='CONNECT',
                    log_level='INFO',
                    message="SMTP connection closed"
                )
            except Exception as e:
                EmailLog.log_operation(
                    operation='CONNECT',
                    log_level='WARNING',
                    message=f"Error closing SMTP connection: {str(e)}"
                )
            finally:
                self.connection = None
    
    async def test_connection_async(self):
        """
        Test the SMTP connection asynchronously without sending an email.
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if not await self.connect_async():
            return False, f"Failed to connect to SMTP server: {self.error_message}"
        
        try:
            loop = asyncio.get_event_loop()
            
            def test_connection():
                try:
                    self.connection.noop()
                    return True, "SMTP connection successful!"
                except Exception as e:
                    return False, f"SMTP connection test failed: {str(e)}"
            
            success, message = await loop.run_in_executor(None, test_connection)
            
            if success:
                EmailLog.log_operation(
                    operation='CONNECT',
                    log_level='INFO',
                    message="SMTP connection test successful"
                )
            else:
                EmailLog.log_operation(
                    operation='CONNECT',
                    log_level='ERROR',
                    message=f"SMTP connection test failed: {message}"
                )
            
            return success, message
            
        except Exception as e:
            error_msg = str(e)
            EmailLog.log_operation(
                operation='CONNECT',
                log_level='ERROR',
                message=f"Exception testing SMTP connection: {error_msg}"
            )
            return False, f"SMTP connection test failed: {error_msg}"
        
        finally:
            await self.close_async()


class EmailSenderService:
    """
    High-level email sending service.
    
    Manages the complete email sending workflow including:
    - Queue management
    - Retry logic
    - Logging
    - Rate limiting
    """
    
    def __init__(self):
        self.logger = logger
    
    async def send_email_to_recipients(self, email, recipients, smtp_config):
        """
        Send an email to multiple recipients asynchronously.
        
        Args:
            email: Email instance
            recipients: List of Recipient instances or email addresses
            smtp_config: SmtpConfig instance
            
        Returns:
            dict: {'success': int, 'failed': int, 'errors': list}
        """
        sender = AsyncSmtpEmailSender(smtp_config)
        results = {'success': 0, 'failed': 0, 'errors': []}
        
        try:
            # Connect once for all recipients (persistent connection)
            if not await sender.connect_async():
                error_msg = f"Failed to connect to SMTP server: {sender.error_message}"
                results['errors'].append(error_msg)
                
                # Mark all queue entries as failed
                for recipient in recipients:
                    if isinstance(recipient, Recipient):
                        to_email = recipient.email
                    else:
                        to_email = recipient
                    
                    queue_entry = EmailQueue.objects.create(
                        email=email,
                        recipient=recipient if isinstance(recipient, Recipient) else None,
                        to_email=to_email,
                        status='FAILED',
                        error_message=error_msg
                    )
                    queue_entry.mark_as_failed(error_msg)
                    results['failed'] += 1
                
                return results
            
            # Process each recipient
            for recipient in recipients:
                try:
                    if isinstance(recipient, Recipient):
                        to_email = recipient.email
                        recipient_obj = recipient
                    else:
                        to_email = recipient
                        recipient_obj = None
                    
                    # Create queue entry
                    queue_entry = EmailQueue.objects.create(
                        email=email,
                        recipient=recipient_obj,
                        to_email=to_email,
                        status='PENDING'
                    )
                    
                    # Send email
                    success, message = await sender.send_email_async(
                        from_email=email.from_email,
                        to_email=to_email,
                        subject=email.subject,
                        body=email.body,
                        is_html=email.is_html
                    )
                    
                    if success:
                        queue_entry.mark_as_sent()
                        results['success'] += 1
                        
                        EmailLog.log_operation(
                            email=email,
                            queue_entry=queue_entry,
                            operation='SEND',
                            log_level='INFO',
                            message=f"Successfully sent email to {to_email}"
                        )
                    else:
                        queue_entry.mark_as_failed(message)
                        results['failed'] += 1
                        results['errors'].append(f"{to_email}: {message}")
                        
                        EmailLog.log_operation(
                            email=email,
                            queue_entry=queue_entry,
                            operation='SEND',
                            log_level='ERROR',
                            message=f"Failed to send email to {to_email}: {message}"
                        )
                        
                except Exception as e:
                    error_msg = str(e)
                    results['failed'] += 1
                    results['errors'].append(f"{to_email}: {error_msg}")
                    
                    EmailLog.log_operation(
                        email=email,
                        operation='SEND',
                        log_level='ERROR',
                        message=f"Exception sending to {to_email}: {error_msg}"
                    )
            
            return results
            
        finally:
            await sender.close_async()
    
    async def process_email_queue(self, email):
        """
        Process the email queue for a specific email.
        
        Args:
            email: Email instance to process
            
        Returns:
            dict: {'success': int, 'failed': int, 'retrying': int, 'errors': list}
        """
        results = {'success': 0, 'failed': 0, 'retrying': 0, 'errors': []}
        
        # Get all pending queue entries for this email
        pending_entries = EmailQueue.objects.filter(
            email=email,
            status='PENDING'
        ).order_by('-priority', 'created_at')
        
        if not pending_entries.exists():
            return results
        
        # Get SMTP config from the email
        smtp_config = email.smtp_config
        if not smtp_config:
            # Try to get SMTP config from mailing lists
            for mailing_list in email.mailing_lists.all():
                if mailing_list.smtp_config:
                    smtp_config = mailing_list.smtp_config
                    break
        
        if not smtp_config:
            error_msg = "No SMTP configuration available for this email"
            for entry in pending_entries:
                entry.mark_as_failed(error_msg)
                results['failed'] += 1
                results['errors'].append(f"{entry.to_email}: {error_msg}")
            return results
        
        # Process all pending entries
        sender = AsyncSmtpEmailSender(smtp_config)
        
        try:
            # Connect once for all entries
            if not await sender.connect_async():
                error_msg = f"Failed to connect to SMTP server: {sender.error_message}"
                for entry in pending_entries:
                    entry.mark_as_failed(error_msg)
                    results['failed'] += 1
                    results['errors'].append(f"{entry.to_email}: {error_msg}")
                return results
            
            for entry in pending_entries:
                try:
                    # Mark as sending
                    entry.status = 'SENDING'
                    entry.save()
                    
                    # Send email
                    success, message = await sender.send_email_async(
                        from_email=email.from_email,
                        to_email=entry.to_email,
                        subject=email.subject,
                        body=email.body,
                        is_html=email.is_html
                    )
                    
                    if success:
                        entry.mark_as_sent()
                        results['success'] += 1
                        
                        EmailLog.log_operation(
                            email=email,
                            queue_entry=entry,
                            operation='SEND',
                            log_level='INFO',
                            message=f"Queue entry {entry.id} sent to {entry.to_email}"
                        )
                    else:
                        # Check if we can retry
                        if entry.can_be_retried():
                            entry.status = 'RETRYING'
                            entry.error_message = message
                            entry.save()
                            results['retrying'] += 1
                            
                            EmailLog.log_operation(
                                email=email,
                                queue_entry=entry,
                                operation='RETRY',
                                log_level='WARNING',
                                message=f"Queue entry {entry.id} will be retried: {message}"
                            )
                        else:
                            entry.mark_as_failed(message)
                            results['failed'] += 1
                            results['errors'].append(f"{entry.to_email}: {message}")
                            
                            EmailLog.log_operation(
                                email=email,
                                queue_entry=entry,
                                operation='SEND',
                                log_level='ERROR',
                                message=f"Queue entry {entry.id} failed: {message}"
                            )
                        
                except Exception as e:
                    error_msg = str(e)
                    if entry.can_be_retried():
                        entry.status = 'RETRYING'
                        entry.error_message = error_msg
                        entry.save()
                        results['retrying'] += 1
                    else:
                        entry.mark_as_failed(error_msg)
                        results['failed'] += 1
                        results['errors'].append(f"{entry.to_email}: {error_msg}")
                    
                    EmailLog.log_operation(
                        email=email,
                        queue_entry=entry,
                        operation='SEND',
                        log_level='ERROR',
                        message=f"Exception processing queue entry {entry.id}: {error_msg}"
                    )
            
            return results
            
        finally:
            await sender.close_async()
    
    async def retry_failed_emails(self):
        """
        Retry all failed emails that can be retried.
        
        Returns:
            dict: {'retried': int, 'failed': int, 'errors': list}
        """
        results = {'retried': 0, 'failed': 0, 'errors': []}
        
        # Get all failed queue entries that can be retried
        retryable_entries = EmailQueue.objects.filter(
            status='FAILED',
            attempts__lt=2
        )
        
        for entry in retryable_entries:
            try:
                # Reset status for retry
                entry.status = 'PENDING'
                entry.save()
                
                # Process this specific entry
                email = entry.email
                smtp_config = email.smtp_config
                
                if not smtp_config:
                    for mailing_list in email.mailing_lists.all():
                        if mailing_list.smtp_config:
                            smtp_config = mailing_list.smtp_config
                            break
                
                if not smtp_config:
                    error_msg = "No SMTP configuration available"
                    entry.mark_as_failed(error_msg)
                    results['failed'] += 1
                    results['errors'].append(f"Entry {entry.id}: {error_msg}")
                    continue
                
                sender = AsyncSmtpEmailSender(smtp_config)
                
                try:
                    if await sender.connect_async():
                        success, message = await sender.send_email_async(
                            from_email=email.from_email,
                            to_email=entry.to_email,
                            subject=email.subject,
                            body=email.body,
                            is_html=email.is_html
                        )
                        
                        if success:
                            entry.mark_as_sent()
                            results['retried'] += 1
                            
                            EmailLog.log_operation(
                                email=email,
                                queue_entry=entry,
                                operation='RETRY',
                                log_level='INFO',
                                message=f"Queue entry {entry.id} retried successfully"
                            )
                        else:
                            entry.mark_as_failed(message)
                            results['failed'] += 1
                            results['errors'].append(f"Entry {entry.id}: {message}")
                            
                            EmailLog.log_operation(
                                email=email,
                                queue_entry=entry,
                                operation='RETRY',
                                log_level='ERROR',
                                message=f"Queue entry {entry.id} retry failed: {message}"
                            )
                    else:
                        error_msg = f"Failed to connect: {sender.error_message}"
                        entry.mark_as_failed(error_msg)
                        results['failed'] += 1
                        results['errors'].append(f"Entry {entry.id}: {error_msg}")
                
                finally:
                    await sender.close_async()
                    
            except Exception as e:
                error_msg = str(e)
                entry.mark_as_failed(error_msg)
                results['failed'] += 1
                results['errors'].append(f"Entry {entry.id}: {error_msg}")
                
                EmailLog.log_operation(
                    email=entry.email,
                    queue_entry=entry,
                    operation='RETRY',
                    log_level='ERROR',
                    message=f"Exception retrying queue entry {entry.id}: {error_msg}"
                )
        
        return results


# Synchronous wrapper functions for compatibility
# These allow the async sender to be used from synchronous contexts

def send_email_sync(email, recipients, smtp_config):
    """
    Send an email synchronously (wrapper for async version).
    
    Args:
        email: Email instance
        recipients: List of Recipient instances or email addresses
        smtp_config: SmtpConfig instance
        
    Returns:
        dict: Results from async sending
    """
    import asyncio
    
    service = EmailSenderService()
    
    # Run async function in a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(
            service.send_email_to_recipients(email, recipients, smtp_config)
        )
    finally:
        loop.close()


def process_queue_sync(email):
    """
    Process email queue synchronously (wrapper for async version).
    
    Args:
        email: Email instance
        
    Returns:
        dict: Results from queue processing
    """
    import asyncio
    
    service = EmailSenderService()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(service.process_email_queue(email))
    finally:
        loop.close()


def retry_failed_sync():
    """
    Retry failed emails synchronously (wrapper for async version).
    
    Returns:
        dict: Results from retry operation
    """
    import asyncio
    
    service = EmailSenderService()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(service.retry_failed_emails())
    finally:
        loop.close()


# Rate limiting utility (AD-009)
class RateLimiter:
    """
    Simple rate limiter for email sending.
    
    Implements the rate limiting requirement: one email job per minute.
    """
    
    def __init__(self):
        self.last_send_time = None
    
    def can_send(self):
        """
        Check if an email can be sent based on rate limiting.
        
        Returns:
            bool: True if email can be sent, False if rate limited
        """
        import time
        
        if self.last_send_time is None:
            return True
        
        current_time = time.time()
        time_since_last = current_time - self.last_send_time
        
        # Allow one email per minute (60 seconds)
        return time_since_last >= 60
    
    def record_send(self):
        """Record that an email was sent."""
        import time
        self.last_send_time = time.time()
    
    def time_until_next(self):
        """
        Get time remaining until next email can be sent.
        
        Returns:
            float: Seconds until next email can be sent
        """
        import time
        
        if self.last_send_time is None:
            return 0
        
        current_time = time.time()
        time_since_last = current_time - self.last_send_time
        
        if time_since_last >= 60:
            return 0
        
        return 60 - time_since_last


# Global rate limiter instance
rate_limiter = RateLimiter()


def check_rate_limit():
    """
    Check if email sending is allowed based on rate limiting.
    
    Returns:
        tuple: (allowed: bool, wait_time: float)
    """
    if rate_limiter.can_send():
        return True, 0
    else:
        wait_time = rate_limiter.time_until_next()
        return False, wait_time


def record_email_send():
    """Record that an email was sent for rate limiting purposes."""
    rate_limiter.record_send()


# Bounce handling utility (AD-009)
class BounceHandler:
    """
    Utility for handling bounce messages.
    
    Parses bounce messages and updates email/queue records accordingly.
    """
    
    @staticmethod
    def parse_bounce_message(bounce_text):
        """
        Parse a bounce message to extract useful information.
        
        Args:
            bounce_text: The bounce message text
            
        Returns:
            dict: Parsed bounce information
        """
        # Simple parsing - this would be enhanced based on actual bounce formats
        parsed = {
            'type': 'unknown',
            'reason': '',
            'recipient': None,
            'original_message_id': None
        }
        
        # Look for common bounce patterns
        bounce_text_lower = bounce_text.lower()
        
        if 'mailbox full' in bounce_text_lower:
            parsed['type'] = 'mailbox_full'
            parsed['reason'] = 'Mailbox is full'
        elif 'user unknown' in bounce_text_lower or 'recipient not found' in bounce_text_lower:
            parsed['type'] = 'user_unknown'
            parsed['reason'] = 'Recipient not found'
        elif 'message rejected' in bounce_text_lower:
            parsed['type'] = 'rejected'
            parsed['reason'] = 'Message rejected by server'
        elif 'spam' in bounce_text_lower:
            parsed['type'] = 'spam'
            parsed['reason'] = 'Message flagged as spam'
        else:
            parsed['type'] = 'unknown'
            parsed['reason'] = 'Unknown bounce reason'
        
        return parsed
    
    @staticmethod
    def handle_bounce(email, bounce_text, recipient_email=None):
        """
        Handle a bounce message for an email.
        
        Args:
            email: Email instance
            bounce_text: The bounce message text
            recipient_email: Specific recipient email (optional)
        """
        parsed = BounceHandler.parse_bounce_message(bounce_text)
        
        # Log the bounce
        EmailLog.log_operation(
            email=email,
            operation='BOUNCE',
            log_level='WARNING',
            message=f"Bounce received: {parsed['type']} - {parsed['reason']}",
            details={
                'bounce_type': parsed['type'],
                'reason': parsed['reason'],
                'recipient': recipient_email,
                'bounce_text': bounce_text[:500]  # Limit size for logging
            }
        )
        
        # Update email bounce message
        if email:
            email.bounce_message = f"{parsed['type']}: {parsed['reason']}"
            email.save()
        
        # Update queue entries for this recipient
        if recipient_email:
            queue_entries = EmailQueue.objects.filter(
                email=email,
                to_email=recipient_email
            )
            
            for entry in queue_entries:
                entry.error_message = f"Bounce: {parsed['type']} - {parsed['reason']}"
                entry.save()


# Email validation utility
class EmailValidator:
    """
    Utility for validating email content and recipients.
    """
    
    @staticmethod
    def validate_email_content(subject, body, from_email, recipients):
        """
        Validate email content before sending.
        
        Args:
            subject: Email subject
            body: Email body
            from_email: Sender email
            recipients: List of recipient emails
            
        Returns:
            tuple: (is_valid: bool, errors: list)
        """
        errors = []
        
        # Validate subject
        if not subject or not subject.strip():
            errors.append("Subject cannot be empty")
        
        if len(subject) > 500:
            errors.append("Subject is too long (max 500 characters)")
        
        # Validate body
        if not body or not body.strip():
            errors.append("Body cannot be empty")
        
        # Validate from_email
        from django.core.validators import EmailValidator as DjangoEmailValidator
        validator = DjangoEmailValidator(message="Invalid email address")
        
        try:
            validator(from_email)
        except Exception as e:
            errors.append(f"Invalid from email: {str(e)}")
        
        # Validate recipients
        if not recipients:
            errors.append("At least one recipient is required")
        else:
            for recipient in recipients:
                if isinstance(recipient, str):
                    email = recipient
                elif hasattr(recipient, 'email'):
                    email = recipient.email
                else:
                    errors.append(f"Invalid recipient: {recipient}")
                    continue
                
                try:
                    validator(email)
                except Exception as e:
                    errors.append(f"Invalid recipient email {email}: {str(e)}")
        
        return len(errors) == 0, errors


# Management command utilities for cleanup (AD-007)
def cleanup_old_emails(days=14):
    """
    Clean up emails older than specified days.
    
    Args:
        days: Number of days to keep emails (default: 14)
        
    Returns:
        tuple: (deleted_count: int, error_count: int)
    """
    from django.utils import timezone
    
    cutoff = timezone.now() - timezone.timedelta(days=days)
    
    # Delete old emails
    old_emails = Email.objects.filter(created_at__lt=cutoff)
    deleted_count = old_emails.count()
    
    # Also delete related queue entries and logs
    old_queue = EmailQueue.objects.filter(created_at__lt=cutfall)
    queue_deleted = old_queue.delete()
    
    old_logs = EmailLog.objects.filter(created_at__lt=cutoff)
    logs_deleted = old_logs.delete()
    
    # Delete the emails
    email_deleted = old_emails.delete()
    
    EmailLog.log_operation(
        operation='QUEUE',
        log_level='INFO',
        message=f"Cleaned up {deleted_count} old emails, {queue_deleted[0]} queue entries, {logs_deleted[0]} log entries"
    )
    
    return deleted_count, 0


def cleanup_old_queue_entries(days=14):
    """
    Clean up queue entries older than specified days.
    
    Args:
        days: Number of days to keep queue entries (default: 14)
        
    Returns:
        int: Number of deleted queue entries
    """
    from django.utils import timezone
    
    cutoff = timezone.now() - timezone.timedelta(days=days)
    
    # Only delete completed entries (SENT or FAILED)
    old_entries = EmailQueue.objects.filter(
        created_at__lt=cutoff,
        status__in=['SENT', 'FAILED']
    )
    
    deleted_count = old_entries.count()
    old_entries.delete()
    
    EmailLog.log_operation(
        operation='QUEUE',
        log_level='INFO',
        message=f"Cleaned up {deleted_count} old queue entries"
    )
    
    return deleted_count
