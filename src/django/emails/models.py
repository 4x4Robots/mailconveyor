# Emails app models
# AD-004: Async email sending with queue and retry logic
# AD-007: 14-day retention for sent emails
# AD-008: File system for attachments
# AD-009: Rate limiting and bounce logging

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import EmailValidator
import logging

# Set up logging for email operations
logger = logging.getLogger(__name__)


class EmailTemplate(models.Model):
    """
    Email template model.
    
    Stores reusable email templates that can be used for composing emails.
    Templates can be global or specific to a mailing list.
    """
    
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Unique name for the template"
    )
    
    subject = models.CharField(
        max_length=500,
        help_text="Email subject template"
    )
    
    body = models.TextField(
        help_text="Email body template (HTML allowed)"
    )
    
    is_html = models.BooleanField(
        default=True,
        help_text="Whether the body contains HTML"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the template was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the template was last updated"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_email_templates',
        help_text="User who created this template"
    )
    
    # Optional relationship to MailingList for list-specific templates
    mailing_list = models.ForeignKey(
        'mailinglists.MailingList',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_templates',
        help_text="Mailing list this template belongs to (optional)"
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Email Template'
        verbose_name_plural = 'Email Templates'
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('emails:template_detail', kwargs={'pk': self.pk})


class Email(models.Model):
    """
    Email model.
    
    Represents an email that has been composed and potentially sent.
    Tracks the status and metadata of email sending operations.
    
    Status workflow:
    - DRAFT: Email is being composed, not yet sent
    - QUEUED: Email is in the queue waiting to be sent
    - SENDING: Email is currently being sent
    - SENT: Email was successfully sent
    - FAILED: Email sending failed
    - RETRYING: Email is being retried after failure
    """
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('QUEUED', 'Queued'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('RETRYING', 'Retrying'),
    ]
    
    subject = models.CharField(
        max_length=500,
        help_text="Email subject"
    )
    
    body = models.TextField(
        help_text="Email body content"
    )
    
    is_html = models.BooleanField(
        default=False,
        help_text="Whether the body contains HTML"
    )
    
    from_email = models.EmailField(
        help_text="Sender email address",
        validators=[EmailValidator(message="Please enter a valid email address")]
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        help_text="Current status of the email"
    )
    
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the email was successfully sent"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the email was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the email was last updated"
    )
    
    # ForeignKey to the user who created/sent this email
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_emails',
        help_text="User who created this email"
    )
    
    # Many-to-many relationship with recipients
    recipients = models.ManyToManyField(
        'recipients.Recipient',
        related_name='received_emails',
        blank=True,
        help_text="Recipients of this email"
    )
    
    # Many-to-many relationship with mailing lists (for sending to entire lists)
    mailing_lists = models.ManyToManyField(
        'mailinglists.MailingList',
        related_name='sent_emails',
        blank=True,
        help_text="Mailing lists to send this email to"
    )
    
    # ForeignKey to SMTP config used for sending
    smtp_config = models.ForeignKey(
        'mailinglists.SmtpConfig',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_emails',
        help_text="SMTP configuration used to send this email"
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if email sending failed"
    )
    
    # Retry tracking
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of attempts to send this email"
    )
    
    # Bounce tracking (AD-009)
    bounce_message = models.TextField(
        blank=True,
        null=True,
        help_text="Bounce message if email was returned"
    )
    
    # Logging metadata
    log_file = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Path to log file for this email operation"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email'
        verbose_name_plural = 'Emails'
        
        # Indexes for better query performance
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['sent_at']),
            models.Index(fields=['created_by']),
        ]
    
    def __str__(self):
        return f"{self.subject} ({self.status})"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('emails:detail', kwargs={'pk': self.pk})
    
    def get_recipient_count(self):
        """Get the total number of recipients for this email."""
        return self.recipients.count()
    
    def get_mailing_list_count(self):
        """Get the total number of mailing lists for this email."""
        return self.mailing_lists.count()
    
    def get_all_recipients(self):
        """Get all recipients including those from mailing lists."""
        recipients = list(self.recipients.all())
        
        # Add recipients from mailing lists
        for mailing_list in self.mailing_lists.all():
            for recipient in mailing_list.recipients.all():
                if recipient not in recipients:
                    recipients.append(recipient)
        
        return recipients
    
    def get_unique_recipient_emails(self):
        """Get unique email addresses from all recipients (AD-005 deduplication)."""
        recipients = self.get_all_recipients()
        unique_emails = {}
        
        for recipient in recipients:
            if recipient.email not in unique_emails:
                unique_emails[recipient.email] = recipient
        
        return list(unique_emails.values())
    
    def can_be_retried(self):
        """Check if this email can be retried."""
        return (self.status == 'FAILED' and 
                self.attempts < 2)  # Max 2 attempts total (1 original + 1 retry)
    
    def mark_as_queued(self):
        """Mark the email as queued for sending."""
        self.status = 'QUEUED'
        self.save()
        logger.info(f"Email {self.id} marked as queued: {self.subject}")
    
    def mark_as_sending(self):
        """Mark the email as currently being sent."""
        self.status = 'SENDING'
        self.save()
        logger.info(f"Email {self.id} marked as sending: {self.subject}")
    
    def mark_as_sent(self):
        """Mark the email as successfully sent."""
        self.status = 'SENT'
        self.sent_at = timezone.now()
        self.save()
        logger.info(f"Email {self.id} marked as sent: {self.subject}")
    
    def mark_as_failed(self, error_message=None):
        """Mark the email as failed."""
        self.status = 'FAILED'
        self.attempts += 1
        if error_message:
            self.error_message = error_message
        self.save()
        logger.error(f"Email {self.id} marked as failed: {self.subject}. Error: {error_message}")
    
    def mark_as_retrying(self):
        """Mark the email as being retried."""
        self.status = 'RETRYING'
        self.save()
        logger.info(f"Email {self.id} marked as retrying: {self.subject}")


class EmailAttachment(models.Model):
    """
    Email attachment model.
    
    Stores file attachments for emails.
    Files are stored in the file system (AD-008).
    """
    
    file = models.FileField(
        upload_to='email_attachments/',
        help_text="Attachment file"
    )
    
    filename = models.CharField(
        max_length=255,
        help_text="Original filename of the attachment"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the attachment was uploaded"
    )
    
    # ForeignKey to the email this attachment belongs to
    email = models.ForeignKey(
        Email,
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="Email this attachment belongs to"
    )
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Email Attachment'
        verbose_name_plural = 'Email Attachments'
    
    def __str__(self):
        return f"{self.filename} (for email {self.email.id})"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('emails:attachment_detail', kwargs={'pk': self.pk})


class EmailQueue(models.Model):
    """
    Email queue model for async email sending (AD-004).
    
    Tracks individual email sending operations in the queue.
    Each email can have multiple queue entries (one per recipient).
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('RETRYING', 'Retrying'),
    ]
    
    # ForeignKey to the email being sent
    email = models.ForeignKey(
        Email,
        on_delete=models.CASCADE,
        related_name='queue_entries',
        help_text="Email being sent"
    )
    
    # ForeignKey to the recipient being sent to
    recipient = models.ForeignKey(
        'recipients.Recipient',
        on_delete=models.CASCADE,
        related_name='email_queue_entries',
        help_text="Recipient being sent to"
    )
    
    # Email address being sent to (can be different from recipient.email for direct addresses)
    to_email = models.EmailField(
        help_text="Actual email address being sent to",
        validators=[EmailValidator(message="Please enter a valid email address")]
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text="Current status of this queue entry"
    )
    
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of attempts to send this email"
    )
    
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this email was successfully sent"
    )
    
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if sending failed"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this queue entry was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this queue entry was last updated"
    )
    
    # Priority for queue processing
    priority = models.PositiveIntegerField(
        default=0,
        help_text="Priority level (higher = more priority)"
    )
    
    class Meta:
        ordering = ['-priority', 'created_at']
        verbose_name = 'Email Queue Entry'
        verbose_name_plural = 'Email Queue Entries'
        
        # Indexes for queue processing
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['created_at']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"Queue {self.id}: {self.email.subject} -> {self.to_email} ({self.status})"
    
    def mark_as_sent(self):
        """Mark this queue entry as successfully sent."""
        self.status = 'SENT'
        self.sent_at = timezone.now()
        self.save()
        logger.info(f"Queue entry {self.id} marked as sent: {self.email.subject} -> {self.to_email}")
    
    def mark_as_failed(self, error_message=None):
        """Mark this queue entry as failed."""
        self.status = 'FAILED'
        self.attempts += 1
        if error_message:
            self.error_message = error_message
        self.save()
        logger.error(f"Queue entry {self.id} marked as failed: {self.email.subject} -> {self.to_email}. Error: {error_message}")
    
    def can_be_retried(self):
        """Check if this queue entry can be retried."""
        return (self.status == 'FAILED' and 
                self.attempts < 2)  # Max 2 attempts total (1 original + 1 retry)


class EmailLog(models.Model):
    """
    Email log model for detailed logging of email operations.
    
    Provides comprehensive logging for debugging and auditing.
    """
    
    LOG_LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]
    
    OPERATION_CHOICES = [
        ('CONNECT', 'SMTP Connection'),
        ('AUTH', 'SMTP Authentication'),
        ('SEND', 'Email Send'),
        ('RETRY', 'Retry'),
        ('BOUNCE', 'Bounce Handling'),
        ('QUEUE', 'Queue Operation'),
    ]
    
    # ForeignKey to the email (optional, for general logs)
    email = models.ForeignKey(
        Email,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        help_text="Email this log entry relates to"
    )
    
    # ForeignKey to the queue entry (optional)
    queue_entry = models.ForeignKey(
        EmailQueue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        help_text="Queue entry this log entry relates to"
    )
    
    log_level = models.CharField(
        max_length=10,
        choices=LOG_LEVEL_CHOICES,
        default='INFO',
        help_text="Severity level of the log entry"
    )
    
    operation = models.CharField(
        max_length=20,
        choices=OPERATION_CHOICES,
        help_text="Type of operation being logged"
    )
    
    message = models.TextField(
        help_text="Log message"
    )
    
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional details in JSON format"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the log entry was created"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Logs'
        
        # Indexes for log queries
        indexes = [
            models.Index(fields=['log_level']),
            models.Index(fields=['operation']),
            models.Index(fields=['created_at']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"[{self.log_level}] {self.operation}: {self.message[:50]}"
    
    @classmethod
    def log_operation(cls, email=None, queue_entry=None, operation=None, 
                     log_level='INFO', message='', details=None):
        """
        Convenience method to create a log entry.
        
        Args:
            email: Email instance (optional)
            queue_entry: EmailQueue instance (optional)
            operation: Operation type from OPERATION_CHOICES
            log_level: Log level from LOG_LEVEL_CHOICES
            message: Log message
            details: Additional details as dict
        
        Returns:
            EmailLog instance
        """
        log_entry = cls(
            email=email,
            queue_entry=queue_entry,
            operation=operation,
            log_level=log_level,
            message=message,
            details=details or {}
        )
        log_entry.save()
        
        # Also log to Python logging
        logger.log(
            getattr(logging, log_level.upper(), logging.INFO),
            f"[{operation}] {message}"
        )
        
        return log_entry