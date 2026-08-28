# MailingLists app forms

from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from .models import MailingList, SmtpConfig
from accounts.utils import is_admin, is_manager


class MailingListForm(forms.ModelForm):
    """Form for creating and updating mailing lists."""
    
    class Meta:
        model = MailingList
        fields = ['name', 'description', 'users_with_access']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'users_with_access': forms.SelectMultiple(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # If this is an existing mailing list, only show users that the current user can manage
        if self.instance and self.instance.pk and self.request:
            from accounts.utils import is_admin, is_manager
            
            if is_admin(self.request.user):
                # Admin can see all users
                pass
            elif is_manager(self.request.user):
                # Manager can only see users they have access to
                # For now, managers can see all users but this could be restricted further
                pass
            else:
                # Regular users can only see themselves
                self.fields['users_with_access'].queryset = User.objects.filter(pk=self.request.user.pk)
        elif self.request:
            # For new mailing lists, restrict user selection based on role
            if is_admin(self.request.user):
                # Admin can select any user
                pass
            elif is_manager(self.request.user):
                # Manager can select any user
                pass
            else:
                # Regular users can only select themselves
                self.fields['users_with_access'].queryset = User.objects.filter(pk=self.request.user.pk)
    
    def save(self, commit=True, created_by=None):
        """Save the mailing list with the created_by field set."""
        instance = super().save(commit=False)
        
        if created_by:
            instance.created_by = created_by
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


class SmtpConfigForm(forms.ModelForm):
    """Form for SMTP configuration."""
    
    # Use plain text password field - encryption happens in the model
    password = forms.CharField(
        label=_("SMTP Password"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Password will be encrypted before storage (AD-003)"
    )
    
    class Meta:
        model = SmtpConfig
        fields = ['host', 'port', 'username', 'password', 'use_tls', 'use_ssl', 'default_from_email']
        widgets = {
            'host': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'use_tls': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'use_ssl': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_from_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing existing config, don't show the password
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['password'].widget = forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Leave blank to keep current password'
            })
    
    def save(self, commit=True):
        """Save the SMTP config, handling password encryption."""
        instance = super().save(commit=False)
        
        # Handle password - if it's provided, set it (will be encrypted by model)
        password = self.cleaned_data.get('password')
        if password:
            instance.set_password(password)
        
        if commit:
            instance.save()
        
        return instance


class MailingListAccessForm(forms.Form):
    """Form for managing user access to a mailing list."""
    
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        label=_("Users with Access"),
        help_text="Select users who should have access to this mailing list"
    )
    
    def __init__(self, *args, **kwargs):
        self.mailing_list = kwargs.pop('mailing_list', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.mailing_list:
            # Set initial selected users
            initial = self.mailing_list.users_with_access.values_list('pk', flat=True)
            self.fields['users'].initial = initial
        
        # Restrict queryset based on user role
        if self.request:
            from accounts.utils import is_admin, is_manager
            
            if is_admin(self.request.user):
                # Admin can see all users
                pass
            elif is_manager(self.request.user):
                # Manager can see all users
                pass
            else:
                # Regular users can only see themselves
                self.fields['users'].queryset = User.objects.filter(pk=self.request.user.pk)
    
    def save(self):
        """Update the mailing list's users_with_access."""
        if self.mailing_list:
            users = self.cleaned_data['users']
            self.mailing_list.users_with_access.set(users)
            return self.mailing_list
        return None