# Recipients app forms
# AD-005: Recipient uniqueness by (first_name, last_name, email)

from django import forms
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
from .models import Recipient


class RecipientForm(forms.ModelForm):
    """
    Form for creating and updating recipients.
    """
    
    class Meta:
        model = Recipient
        fields = ['first_name', 'last_name', 'email', 'mailing_lists']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
            'mailing_lists': forms.SelectMultiple(attrs={
                'class': 'form-select',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter mailing lists to only those the user has access to
        if user and user.is_authenticated:
            from mailinglists.models import MailingList
            from django.db.models import Q
            
            # AD-002: Filter by object-level permissions
            if user.is_app_admin or user.is_app_manager:
                # Admins and managers can see all mailing lists
                mailing_lists = MailingList.objects.all()
            else:
                # Other users can only see mailing lists they have access to
                mailing_lists = MailingList.objects.filter(
                    Q(users_with_access=user) | Q(created_by=user)
                ).distinct()
            
            self.fields['mailing_lists'].queryset = mailing_lists
        else:
            self.fields['mailing_lists'].queryset = []
    
    def clean_email(self):
        """Validate email format."""
        email = self.cleaned_data.get('email')
        if email:
            validator = EmailValidator(message="Please enter a valid email address")
            try:
                validator(email)
            except ValidationError as e:
                raise forms.ValidationError(str(e))
        return email
    
    def clean(self):
        """Validate the form data."""
        cleaned_data = super().clean()
        
        first_name = cleaned_data.get('first_name')
        last_name = cleaned_data.get('last_name')
        email = cleaned_data.get('email')
        
        # Check for uniqueness (AD-005)
        if first_name and last_name and email:
            # Check if a recipient with the same identity already exists
            # Exclude the current instance if this is an update
            if self.instance.pk:
                existing = Recipient.objects.filter(
                    first_name=first_name,
                    last_name=last_name,
                    email=email
                ).exclude(pk=self.instance.pk).exists()
            else:
                existing = Recipient.objects.filter(
                    first_name=first_name,
                    last_name=last_name,
                    email=email
                ).exists()
            
            if existing:
                raise forms.ValidationError(
                    "A recipient with this name and email already exists."
                )
        
        return cleaned_data


class RecipientSearchForm(forms.Form):
    """
    Form for searching recipients.
    """
    
    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name or email...'
        })
    )
    
    mailing_list = forms.IntegerField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter mailing lists to only those the user has access to
        if user and user.is_authenticated:
            from mailinglists.models import MailingList
            from django.db.models import Q
            
            if user.is_app_admin or user.is_app_manager:
                mailing_lists = MailingList.objects.all()
            else:
                mailing_lists = MailingList.objects.filter(
                    Q(users_with_access=user) | Q(created_by=user)
                ).distinct()
            
            self.fields['mailing_list'].widget.choices = [
                ('', 'All Mailing Lists')
            ] + [(ml.pk, ml.name) for ml in mailing_lists]
        else:
            self.fields['mailing_list'].widget.choices = [
                ('', 'All Mailing Lists')
            ]


class CSVImportForm(forms.Form):
    """
    Form for uploading CSV files for recipient import.
    """
    
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with columns: first_name, last_name, email',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        })
    )
    
    mailing_list = forms.IntegerField(
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter mailing lists to only those the user has access to
        if user and user.is_authenticated:
            from mailinglists.models import MailingList
            from django.db.models import Q
            
            if user.is_app_admin or user.is_app_manager:
                mailing_lists = MailingList.objects.all()
            else:
                mailing_lists = MailingList.objects.filter(
                    Q(users_with_access=user) | Q(created_by=user)
                ).distinct()
            
            self.fields['mailing_list'].widget.choices = [
                ('', 'Select Mailing List (optional)')
            ] + [(ml.pk, ml.name) for ml in mailing_lists]
        else:
            self.fields['mailing_list'].widget.choices = [
                ('', 'Select Mailing List (optional)')
            ]
