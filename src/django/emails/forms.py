# Emails app forms
# AD-004: Async email sending with queue and retry logic
# AD-005: Recipient deduplication

from django import forms
from django.core.validators import EmailValidator
from django.contrib.auth.models import User
from .models import Email, EmailTemplate, EmailAttachment
from recipients.models import Recipient
from mailinglists.models import MailingList


class EmailTemplateForm(forms.ModelForm):
    """Form for creating and updating email templates."""
    
    class Meta:
        model = EmailTemplate
        fields = ['name', 'subject', 'body', 'is_html', 'mailing_list']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'is_html': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mailing_list': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name and len(name) > 200:
            raise forms.ValidationError("Name is too long (max 200 characters)")
        return name
    
    def clean_subject(self):
        subject = self.cleaned_data.get('subject')
        if subject and len(subject) > 500:
            raise forms.ValidationError("Subject is too long (max 500 characters)")
        return subject


class EmailComposerForm(forms.ModelForm):
    """Form for composing emails."""
    
    # Override recipients to be a multiple choice field
    recipients = forms.ModelMultipleChoiceField(
        queryset=Recipient.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        label="Individual Recipients"
    )
    
    # Override mailing_lists to be a multiple choice field
    mailing_lists = forms.ModelMultipleChoiceField(
        queryset=MailingList.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        label="Mailing Lists"
    )
    
    # Add template choice
    template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Template (optional)"
    )
    
    class Meta:
        model = Email
        fields = ['subject', 'body', 'is_html', 'from_email']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 15}),
            'is_html': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'from_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If this is an existing email instance, set initial data for custom fields
        if 'instance' in kwargs and kwargs['instance']:
            instance = kwargs['instance']
            self.fields['recipients'].initial = instance.recipients.all()
            self.fields['mailing_lists'].initial = instance.mailing_lists.all()
            if hasattr(instance, 'template') and instance.template:
                self.fields['template'].initial = instance.template
        
        if user:
            # Filter recipients and mailing lists by user access
            from mailinglists.models import MailingList
            
            # Get mailing lists the user has access to
            # Get recipients from accessible mailing lists
            accessible_lists = MailingList.objects.filter(
                users_with_access=user
            )
            
            # Get recipients from accessible mailing lists
            accessible_recipients = Recipient.objects.filter(
                mailing_lists__in=accessible_lists
            )
            
            # Also include recipients created by the user
            user_recipients = Recipient.objects.filter(created_by=user)
            
            # Combine queries - Django doesn't support distinct() after union()
            # So we'll use a list to deduplicate
            recipient_ids = set()
            all_recipients = []
            
            for recipient in accessible_recipients:
                if recipient.id not in recipient_ids:
                    all_recipients.append(recipient)
                    recipient_ids.add(recipient.id)
            
            for recipient in user_recipients:
                if recipient.id not in recipient_ids:
                    all_recipients.append(recipient)
                    recipient_ids.add(recipient.id)
            
            self.fields['recipients'].queryset = Recipient.objects.filter(id__in=recipient_ids)
            self.fields['mailing_lists'].queryset = accessible_lists
            
            # Filter templates by accessible mailing lists or user-created
            user_templates = EmailTemplate.objects.filter(created_by=user)
            list_templates = EmailTemplate.objects.filter(
                mailing_list__in=accessible_lists
            )
            global_templates = EmailTemplate.objects.filter(mailing_list__isnull=True)
            
            # Combine template queries without using union() + distinct()
            template_ids = set()
            all_template_ids = []
            
            for template in user_templates:
                if template.id not in template_ids:
                    all_template_ids.append(template.id)
                    template_ids.add(template.id)
            
            for template in list_templates:
                if template.id not in template_ids:
                    all_template_ids.append(template.id)
                    template_ids.add(template.id)
                    
            for template in global_templates:
                if template.id not in template_ids:
                    all_template_ids.append(template.id)
                    template_ids.add(template.id)
            
            self.fields['template'].queryset = EmailTemplate.objects.filter(id__in=all_template_ids)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Check that at least one recipient or mailing list is selected
        recipients = cleaned_data.get('recipients')
        mailing_lists = cleaned_data.get('mailing_lists')
        
        if not recipients and not mailing_lists:
            raise forms.ValidationError(
                "You must select at least one recipient or mailing list."
            )
        
        # Validate from_email
        from_email = cleaned_data.get('from_email')
        if from_email:
            validator = EmailValidator(message="Please enter a valid email address")
            try:
                validator(from_email)
            except Exception as e:
                self.add_error('from_email', str(e))
        
        # Handle template selection
        template = cleaned_data.get('template')
        if template:
            # If template is selected, use its subject and body as defaults
            if not cleaned_data.get('subject'):
                cleaned_data['subject'] = template.subject
            if not cleaned_data.get('body'):
                cleaned_data['body'] = template.body
            if 'is_html' not in cleaned_data or not cleaned_data.get('is_html'):
                cleaned_data['is_html'] = template.is_html
        
        return cleaned_data
    
    def save(self, commit=True, user=None):
        """Save the email and create queue entries."""
        email = super().save(commit=False)
        
        if user:
            email.created_by = user
        
        # Set initial status
        email.status = 'DRAFT'
        
        if commit:
            email.save()
            
            # Save many-to-many relationships manually since we have custom fields
            if hasattr(self, 'cleaned_data'):
                if 'recipients' in self.cleaned_data and self.cleaned_data['recipients']:
                    email.recipients.set(self.cleaned_data['recipients'])
                if 'mailing_lists' in self.cleaned_data and self.cleaned_data['mailing_lists']:
                    email.mailing_lists.set(self.cleaned_data['mailing_lists'])
        
        return email


class EmailSendForm(forms.Form):
    """Form for sending an existing email (draft)."""
    
    send_now = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Send Immediately"
    )
    
    schedule_for_later = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Schedule for Later"
    )
    
    scheduled_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label="Scheduled Time"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        send_now = cleaned_data.get('send_now')
        schedule_for_later = cleaned_data.get('schedule_for_later')
        scheduled_time = cleaned_data.get('scheduled_time')
        
        if schedule_for_later and not scheduled_time:
            raise forms.ValidationError(
                "You must specify a scheduled time when scheduling for later."
            )
        
        if send_now and schedule_for_later:
            raise forms.ValidationError(
                "You cannot both send now and schedule for later."
            )
        
        return cleaned_data


class EmailAttachmentForm(forms.ModelForm):
    """Form for uploading email attachments."""
    
    class Meta:
        model = EmailAttachment
        fields = ['file', 'filename']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'filename': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (limit to 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError("File size cannot exceed 10MB")
            
            # Check file extension (basic security)
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.csv', '.xls', '.xlsx', 
                                 '.jpg', '.jpeg', '.png', '.gif', '.zip']
            
            import os
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f"File type {ext} is not allowed. Allowed types: {', '.join(allowed_extensions)}"
                )
        
        return file
    
    def save(self, commit=True, email=None):
        """Save the attachment with the specified email."""
        attachment = super().save(commit=False)
        
        if email:
            attachment.email = email
        
        if not attachment.filename and attachment.file:
            attachment.filename = attachment.file.name
        
        if commit:
            attachment.save()
        
        return attachment


class EmailSearchForm(forms.Form):
    """Form for searching emails."""
    
    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search by subject, body, or recipient...'}),
        label="Search"
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + list(Email.STATUS_CHOICES),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Status"
    )
    
    created_by = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Sent By"
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="From Date"
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="To Date"
    )
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        if user:
            # For admin users, show all users; for others, show only themselves
            from django.contrib.auth.models import User
            if user.is_app_admin:
                self.fields['created_by'].queryset = User.objects.all()
            else:
                self.fields['created_by'].queryset = User.objects.filter(pk=user.pk)
