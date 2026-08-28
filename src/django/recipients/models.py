# Recipients app models
# AD-005: Recipient uniqueness by (first_name, last_name, email), deduplicate emails by address
# AD-006: Users and Recipients are separate models

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
from django.utils import timezone


class Recipient(models.Model):
    """
    Email recipient model.
    
    Represents an email recipient who can be part of one or more mailing lists.
    Uniqueness is enforced by the combination of first_name, last_name, and email (AD-005).
    This allows the same email address to be used with different names.
    """
    
    first_name = models.CharField(
        max_length=100,
        help_text="Recipient's first name"
    )
    
    last_name = models.CharField(
        max_length=100,
        help_text="Recipient's last name"
    )
    
    # AD-005: Use Django's EmailValidator for email field
    email = models.EmailField(
        max_length=255,
        help_text="Recipient's email address",
        validators=[EmailValidator(message="Please enter a valid email address")]
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the recipient was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the recipient was last updated"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_recipients',
        help_text="User who created this recipient"
    )
    
    # Many-to-many relationship with MailingList
    mailing_lists = models.ManyToManyField(
        'mailinglists.MailingList',
        related_name='recipients',
        blank=True,
        help_text="Mailing lists this recipient belongs to"
    )
    
    class Meta:
        ordering = ['last_name', 'first_name', 'email']
        verbose_name = 'Recipient'
        verbose_name_plural = 'Recipients'
        
        # AD-005: Uniqueness constraint on (first_name, last_name, email)
        constraints = [
            models.UniqueConstraint(
                fields=['first_name', 'last_name', 'email'],
                name='unique_recipient_identity',
                violation_error_message="A recipient with this name and email already exists."
            )
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>"
    
    def get_full_name(self):
        """Return the full name of the recipient."""
        return f"{self.first_name} {self.last_name}"
    
    def get_absolute_url(self):
        """Get the absolute URL for this recipient."""
        from django.urls import reverse
        return reverse('recipients:detail', kwargs={'pk': self.pk})
    
    def clean(self):
        """Validate the model before saving."""
        super().clean()
        
        # Validate email format
        if self.email:
            validator = EmailValidator(message="Please enter a valid email address")
            try:
                validator(self.email)
            except ValidationError as e:
                raise ValidationError({'email': str(e)})
    
    def save(self, *args, **kwargs):
        """Save the recipient, ensuring validation is run."""
        self.full_clean()
        super().save(*args, **kwargs)


class RecipientImportLog(models.Model):
    """
    Log for tracking CSV import operations.
    
    Stores information about recipient import operations for auditing.
    """
    
    IMPORT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('PARTIAL', 'Partial Success'),
    ]
    
    file_name = models.CharField(
        max_length=255,
        help_text="Name of the imported file"
    )
    
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recipient_imports',
        help_text="User who uploaded the file"
    )
    
    status = models.CharField(
        max_length=20,
        choices=IMPORT_STATUS_CHOICES,
        default='PENDING',
        help_text="Status of the import operation"
    )
    
    total_records = models.PositiveIntegerField(
        default=0,
        help_text="Total number of records in the file"
    )
    
    successful_records = models.PositiveIntegerField(
        default=0,
        help_text="Number of successfully imported records"
    )
    
    failed_records = models.PositiveIntegerField(
        default=0,
        help_text="Number of failed records"
    )
    
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if import failed"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the import was started"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the import was completed"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Recipient Import Log'
        verbose_name_plural = 'Recipient Import Logs'
    
    def __str__(self):
        return f"Import {self.id} - {self.file_name} ({self.status})"
