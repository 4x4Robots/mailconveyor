from django.contrib.auth.models import BaseUserManager
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """Custom user manager for email-only authentication."""
    
    def create_user(self, email, first_name, last_name, password=None, role='USER', **extra_fields):
        """
        Creates and saves a User with the given email, first name, last name and password.
        """
        if not email:
            raise ValueError(_('The Email must be set'))
        
        if not first_name:
            raise ValueError(_('The First Name must be set'))
            
        if not last_name:
            raise ValueError(_('The Last Name must be set'))
        
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, first_name, last_name, password=None, **extra_fields):
        """
        Creates and saves a superuser with the given email, first name, last name and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'ADMIN')
        
        if not email:
            raise ValueError(_('The Email must be set'))
        
        if not first_name:
            raise ValueError(_('The First Name must be set'))
            
        if not last_name:
            raise ValueError(_('The Last Name must be set'))
        
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user