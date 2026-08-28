from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.contrib.auth.models import User, Group
from django.utils.translation import gettext_lazy as _
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


class CustomUserCreationForm(UserCreationForm):
    """Form for creating new users (admin-only)."""
    
    first_name = forms.CharField(
        label=_("First Name"),
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label=_("Last Name"),
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        label=_("Role"),
        choices=[('User', 'User'), ('Manager', 'Manager'), ('Admin', 'Admin')],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'password1', 'password2')
    
    def clean_username(self):
        """Validate that username is a valid email address."""
        username = self.cleaned_data.get('username')
        if username:
            try:
                validate_email(username)
            except ValidationError:
                raise forms.ValidationError(_("Username must be a valid email address."))
        return username
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        # Remove help text for username to keep it simple
        self.fields['username'].help_text = None


class CustomUserChangeForm(UserChangeForm):
    """Form for updating user profiles."""
    
    first_name = forms.CharField(
        label=_("First Name"),
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label=_("Last Name"),
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        label=_("Role"),
        choices=[('User', 'User'), ('Manager', 'Manager'), ('Admin', 'Admin')],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'is_active')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].help_text = None
        # Remove password field
        if 'password' in self.fields:
            del self.fields['password']


class CustomAuthenticationForm(AuthenticationForm):
    """Custom authentication form using username."""
    
    username = forms.CharField(
        label=_("Username"),
        widget=forms.TextInput(attrs={'class': 'form-control', 'autofocus': True})
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )


class ProfileUpdateForm(forms.ModelForm):
    """Form for users to update their own profile."""
    
    first_name = forms.CharField(
        label=_("First Name"),
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label=_("Last Name"),
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name')
    
    def clean_username(self):
        """Validate that username is a valid email address."""
        username = self.cleaned_data.get('username')
        if username:
            try:
                validate_email(username)
            except ValidationError:
                raise forms.ValidationError(_("Username must be a valid email address."))
        return username
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].help_text = None