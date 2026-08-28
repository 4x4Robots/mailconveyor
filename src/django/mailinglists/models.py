# MailingLists app models
# AD-001: Use Django native capabilities
# AD-002: django-guardian for object-level permissions
# AD-003: Fernet encryption for SMTP passwords

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os


# AD-003: Fernet encryption for SMTP passwords
class EncryptionUtils:
    """Utility class for encrypting and decrypting sensitive data."""
    
    @staticmethod
    def get_fernet():
        """Get Fernet instance from Django settings."""
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise ImportError("cryptography package is required for SMTP password encryption. "
                            "Install with: pip install cryptography")
        
        from django.conf import settings
        fernet_key = getattr(settings, 'FERNET_KEY', None)
        if not fernet_key:
            fernet_key = os.environ.get('FERNET_KEY')
        if not fernet_key:
            raise ValueError("FERNET_KEY is not configured. Set it in Django settings or as an environment variable. "
                           "Generate with: from cryptography.fernet import Fernet; Fernet.generate_key()")
        return Fernet(fernet_key.encode())
    
    @staticmethod
    def encrypt(value):
        """Encrypt a string value."""
        if not value:
            return value
        fernet = EncryptionUtils.get_fernet()
        return fernet.encrypt(value.encode()).decode()
    
    @staticmethod
    def decrypt(encrypted_value):
        """Decrypt an encrypted string value."""
        if not encrypted_value:
            return encrypted_value
        fernet = EncryptionUtils.get_fernet()
        return fernet.decrypt(encrypted_value.encode()).decode()


class MailingList(models.Model):
    """
    Mailing list model.
    
    Represents a collection of recipients and email sending configuration.
    Access is controlled via django-guardian object-level permissions (AD-002).
    """
    
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Unique name for the mailing list"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description of the mailing list purpose"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the mailing list was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the mailing list was last updated"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_mailinglists',
        help_text="User who created this mailing list"
    )
    
    # Many-to-many relationship with users who have access to this list
    users_with_access = models.ManyToManyField(
        User,
        related_name='accessible_mailinglists',
        blank=True,
        help_text="Users who have access to this mailing list"
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Mailing List'
        verbose_name_plural = 'Mailing Lists'
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('mailinglists:detail', kwargs={'pk': self.pk})


class SmtpConfig(models.Model):
    """
    SMTP configuration for a mailing list.
    
    Each mailing list has its own SMTP configuration.
    Passwords are encrypted using Fernet (AD-003).
    """
    
    # One-to-one relationship with MailingList
    mailing_list = models.OneToOneField(
        MailingList,
        on_delete=models.CASCADE,
        related_name='smtp_config',
        help_text="The mailing list this SMTP config belongs to"
    )
    
    host = models.CharField(
        max_length=255,
        help_text="SMTP server hostname or IP address"
    )
    
    port = models.PositiveIntegerField(
        default=587,
        help_text="SMTP server port"
    )
    
    username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="SMTP authentication username"
    )
    
    # AD-003: Encrypted password storage
    _password = models.TextField(
        blank=True,
        null=True,
        db_column='password',
        help_text="Encrypted SMTP password"
    )
    
    use_tls = models.BooleanField(
        default=True,
        help_text="Use TLS for secure connection"
    )
    
    use_ssl = models.BooleanField(
        default=False,
        help_text="Use SSL for secure connection"
    )
    
    default_from_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Default 'From' email address for emails sent from this list"
    )
    
    class Meta:
        verbose_name = 'SMTP Configuration'
        verbose_name_plural = 'SMTP Configurations'
    
    def __str__(self):
        return f"SMTP Config for {self.mailing_list.name}"
    
    @property
    def password(self):
        """Decrypt and return the password."""
        if self._password:
            return EncryptionUtils.decrypt(self._password)
        return None
    
    @password.setter
    def password(self, value):
        """Encrypt and store the password."""
        if value:
            self._password = EncryptionUtils.encrypt(value)
        else:
            self._password = None
    
    def get_password(self):
        """Get the decrypted password."""
        return self.password
    
    def set_password(self, value):
        """Set the password (will be encrypted)."""
        self.password = value
    
    def save(self, *args, **kwargs):
        """Save the model, ensuring password is encrypted."""
        # If password is being set as plain text, encrypt it
        if hasattr(self, '_password') and self._password:
            # Check if it's already encrypted by trying to decrypt it
            try:
                # Test if it's already encrypted
                EncryptionUtils.decrypt(self._password)
                # If we get here, it's already encrypted, so leave it as is
            except:
                # Not encrypted, so encrypt it
                self._password = EncryptionUtils.encrypt(self._password)
        super().save(*args, **kwargs)