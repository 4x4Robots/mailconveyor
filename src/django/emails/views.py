# Emails app views
# AD-004: Async email sending with queue and retry logic
# AD-007: 14-day retention for sent emails
# AD-009: Rate limiting and bounce logging

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.db.models import Q
import logging

from .models import Email, EmailTemplate, EmailAttachment, EmailQueue, EmailLog
from .forms import EmailComposerForm, EmailSendForm, EmailTemplateForm, EmailAttachmentForm, EmailSearchForm
from .utils import EmailSenderService, send_email_sync, check_rate_limit, record_email_send
from mailinglists.models import MailingList, SmtpConfig
from recipients.models import Recipient
from accounts.utils import is_admin, is_manager, get_user_role

# Set up logging
logger = logging.getLogger(__name__)


# Permission mixins
class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to require admin permissions."""
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "You need admin permissions to access this page.")
        return redirect('accounts:user_list')


class ManagerRequiredMixin(UserPassesTestMixin):
    """Mixin to require manager or admin permissions."""
    
    def test_func(self):
        return is_manager(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "You need manager permissions to access this page.")
        return redirect('accounts:user_list')


# Helper function to check if user has access to an email
# For now, users can access emails they created or emails sent to lists they have access to
def user_has_email_access(user, email):
    """Check if user has access to view/edit an email."""
    if is_admin(user):
        return True
    
    # Check if user created the email
    if email.created_by == user:
        return True
    
    # Check if user has access to any of the email's mailing lists
    for mailing_list in email.mailing_lists.all():
        if user in mailing_list.users_with_access.all():
            return True
    
    # Check if user has access to any of the email's recipients' mailing lists
    for recipient in email.recipients.all():
        for mailing_list in recipient.mailing_lists.all():
            if user in mailing_list.users_with_access.all():
                return True
    
    return False


# Helper function to get accessible emails for a user
def get_accessible_emails(user):
    """Get all emails accessible to a user."""
    if is_admin(user):
        return Email.objects.all()
    
    # Get emails created by the user
    user_emails = Email.objects.filter(created_by=user)
    
    # Get emails sent to mailing lists the user has access to
    accessible_lists = MailingList.objects.filter(users_with_access=user)
    list_emails = Email.objects.filter(mailing_lists__in=accessible_lists).distinct()
    
    # Get emails sent to recipients in mailing lists the user has access to
    accessible_recipients = Recipient.objects.filter(mailing_lists__in=accessible_lists).distinct()
    recipient_emails = Email.objects.filter(recipients__in=accessible_recipients).distinct()
    
    # Combine all queries without using union().distinct()
    email_ids = set()
    all_emails = []
    
    for email in user_emails:
        if email.id not in email_ids:
            all_emails.append(email)
            email_ids.add(email.id)
    
    for email in list_emails:
        if email.id not in email_ids:
            all_emails.append(email)
            email_ids.add(email.id)
            
    for email in recipient_emails:
        if email.id not in email_ids:
            all_emails.append(email)
            email_ids.add(email.id)
    
    return Email.objects.filter(id__in=email_ids)


# Email Template Views
class EmailTemplateListView(LoginRequiredMixin, ListView):
    """List all email templates accessible to the user."""
    
    model = EmailTemplate
    template_name = 'emails/template_list.html'
    context_object_name = 'templates'
    
    def get_queryset(self):
        """Get templates accessible to the current user."""
        user = self.request.user
        
        if is_admin(user):
            return EmailTemplate.objects.all()
        
        # Get user's own templates
        user_templates = EmailTemplate.objects.filter(created_by=user)
        
        # Get templates for mailing lists the user has access to
        accessible_lists = MailingList.objects.filter(users_with_access=user)
        list_templates = EmailTemplate.objects.filter(mailing_list__in=accessible_lists)
        
        # Get global templates (no mailing list)
        global_templates = EmailTemplate.objects.filter(mailing_list__isnull=True)
        
        # Combine without union().distinct()
        template_ids = set()
        all_templates = []
        
        for template in user_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
        
        for template in list_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
                
        for template in global_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
        
        return EmailTemplate.objects.filter(id__in=template_ids)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Email Templates'
        return context


class EmailTemplateDetailView(LoginRequiredMixin, DetailView):
    """View details of a specific email template."""
    
    model = EmailTemplate
    template_name = 'emails/template_detail.html'
    context_object_name = 'template'
    
    def get_queryset(self):
        """Only allow viewing of accessible templates."""
        user = self.request.user
        
        if is_admin(user):
            return EmailTemplate.objects.all()
        
        # Get user's own templates
        user_templates = EmailTemplate.objects.filter(created_by=user)
        
        # Get templates for mailing lists the user has access to
        accessible_lists = MailingList.objects.filter(users_with_access=user)
        list_templates = EmailTemplate.objects.filter(mailing_list__in=accessible_lists)
        
        # Get global templates
        global_templates = EmailTemplate.objects.filter(mailing_list__isnull=True)
        
        # Combine without union().distinct()
        template_ids = set()
        all_templates = []
        
        for template in user_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
        
        for template in list_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
                
        for template in global_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
        
        return EmailTemplate.objects.filter(id__in=template_ids)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Template: {self.object.name}"
        return context


class EmailTemplateCreateView(ManagerRequiredMixin, CreateView):
    """Create a new email template."""
    
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'emails/template_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('emails:template_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Email Template'
        context['action'] = 'Create'
        return context


class EmailTemplateUpdateView(ManagerRequiredMixin, UpdateView):
    """Update an existing email template."""
    
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'emails/template_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_queryset(self):
        """Only allow editing of accessible templates."""
        user = self.request.user
        
        if is_admin(user):
            return EmailTemplate.objects.all()
        
        # Get user's own templates
        user_templates = EmailTemplate.objects.filter(created_by=user)
        
        # Get templates for mailing lists the user has access to
        accessible_lists = MailingList.objects.filter(users_with_access=user)
        list_templates = EmailTemplate.objects.filter(mailing_list__in=accessible_lists)
        
        # Combine without union().distinct()
        template_ids = set()
        all_templates = []
        
        for template in user_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
        
        for template in list_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
        
        return EmailTemplate.objects.filter(id__in=template_ids)
    
    def form_valid(self, form):
        form.instance.updated_at = timezone.now()
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('emails:template_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Email Template'
        context['action'] = 'Update'
        return context


class EmailTemplateDeleteView(ManagerRequiredMixin, DeleteView):
    """Delete an email template."""
    
    model = EmailTemplate
    template_name = 'emails/template_confirm_delete.html'
    success_url = reverse_lazy('emails:template_list')
    
    def get_queryset(self):
        """Only allow deletion of accessible templates."""
        user = self.request.user
        
        if is_admin(user):
            return EmailTemplate.objects.all()
        
        # Get user's own templates
        user_templates = EmailTemplate.objects.filter(created_by=user)
        
        # Get templates for mailing lists the user has access to
        accessible_lists = MailingList.objects.filter(users_with_access=user)
        list_templates = EmailTemplate.objects.filter(mailing_list__in=accessible_lists)
        
        # Combine without union().distinct()
        template_ids = set()
        all_templates = []
        
        for template in user_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
        
        for template in list_templates:
            if template.id not in template_ids:
                all_templates.append(template)
                template_ids.add(template.id)
        
        return EmailTemplate.objects.filter(id__in=template_ids)


# Email Views
class EmailListView(LoginRequiredMixin, ListView):
    """List all emails accessible to the user."""
    
    model = Email
    template_name = 'emails/email_list.html'
    context_object_name = 'emails'
    paginate_by = 20
    
    def get_queryset(self):
        """Get emails accessible to the current user."""
        return get_accessible_emails(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Emails'
        context['search_form'] = EmailSearchForm(user=self.request.user)
        return context
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests with search parameters."""
        self.request = request
        
        # Check for search parameters
        search_query = request.GET.get('search')
        status_filter = request.GET.get('status')
        created_by_filter = request.GET.get('created_by')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        queryset = self.get_queryset()
        
        # Apply filters
        if search_query:
            queryset = queryset.filter(
                Q(subject__icontains=search_query) |
                Q(body__icontains=search_query) |
                Q(recipients__email__icontains=search_query) |
                Q(recipients__first_name__icontains=search_query) |
                Q(recipients__last_name__icontains=search_query)
            ).distinct()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if created_by_filter:
            queryset = queryset.filter(created_by_id=created_by_filter)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Update the queryset for the list view
        self.object_list = queryset
        
        return super().get(request, *args, **kwargs)


class EmailDetailView(LoginRequiredMixin, DetailView):
    """View details of a specific email."""
    
    model = Email
    template_name = 'emails/email_detail.html'
    context_object_name = 'email'
    
    def get_queryset(self):
        """Only allow viewing of accessible emails."""
        user = self.request.user
        
        if is_admin(user):
            return Email.objects.all()
        
        return get_accessible_emails(user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        email = self.object
        
        context['title'] = f"Email: {email.subject}"
        context['can_edit'] = user_has_email_access(self.request.user, email)
        context['can_send'] = (email.status == 'DRAFT' and 
                             user_has_email_access(self.request.user, email))
        context['queue_entries'] = EmailQueue.objects.filter(email=email).order_by('-created_at')
        context['logs'] = EmailLog.objects.filter(email=email).order_by('-created_at')[:50]
        context['attachments'] = EmailAttachment.objects.filter(email=email)
        
        return context


class EmailCreateView(LoginRequiredMixin, CreateView):
    """Create a new email (compose)."""
    
    model = Email
    form_class = EmailComposerForm
    template_name = 'emails/email_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Save the email with user
        email = form.save(user=self.request.user)
        
        messages.success(self.request, 'Email saved as draft. You can send it later.')
        
        return redirect('emails:detail', pk=email.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Compose Email'
        context['action'] = 'Compose'
        return context


class EmailUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing email (edit draft)."""
    
    model = Email
    form_class = EmailComposerForm
    template_name = 'emails/email_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_queryset(self):
        """Only allow editing of accessible emails that are drafts."""
        user = self.request.user
        
        if is_admin(user):
            return Email.objects.filter(status='DRAFT')
        
        return get_accessible_emails(user).filter(status='DRAFT')
    
    def form_valid(self, form):
        email = form.save(commit=False)
        email.updated_at = timezone.now()
        
        # Save the email first
        email.save()
        
        # Save many-to-many relationships manually
        if 'recipients' in form.cleaned_data:
            email.recipients.set(form.cleaned_data['recipients'])
        if 'mailing_lists' in form.cleaned_data:
            email.mailing_lists.set(form.cleaned_data['mailing_lists'])
        
        messages.success(self.request, 'Email updated successfully.')
        
        return redirect('emails:detail', pk=email.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Email'
        context['action'] = 'Edit'
        return context


class EmailDeleteView(LoginRequiredMixin, DeleteView):
    """Delete an email."""
    
    model = Email
    template_name = 'emails/email_confirm_delete.html'
    success_url = reverse_lazy('emails:list')
    
    def get_queryset(self):
        """Only allow deletion of accessible emails."""
        user = self.request.user
        
        if is_admin(user):
            return Email.objects.all()
        
        return get_accessible_emails(user)


# Email Sending Views
def email_send_view(request, pk):
    """View to send an email (from draft to queue/sent)."""
    email = get_object_or_404(Email, pk=pk)
    
    # Check access
    if not user_has_email_access(request.user, email):
        return HttpResponseForbidden("You don't have permission to send this email.")
    
    # Check if email can be sent (must be DRAFT)
    if email.status != 'DRAFT':
        messages.error(request, f"This email cannot be sent because it's already {email.status}.")
        return redirect('emails:detail', pk=email.pk)
    
    # Check rate limiting
    can_send, wait_time = check_rate_limit()
    if not can_send:
        messages.error(request, f"Email sending is rate limited. Please wait {int(wait_time)} seconds.")
        return redirect('emails:detail', pk=email.pk)
    
    if request.method == 'POST':
        form = EmailSendForm(request.POST)
        if form.is_valid():
            send_now = form.cleaned_data.get('send_now', True)
            
            try:
                # Get SMTP config
                smtp_config = email.smtp_config
                if not smtp_config:
                    # Try to get from mailing lists
                    for mailing_list in email.mailing_lists.all():
                        if mailing_list.smtp_config:
                            smtp_config = mailing_list.smtp_config
                            break
                
                if not smtp_config:
                    messages.error(request, "No SMTP configuration available for this email.")
                    return redirect('emails:detail', pk=email.pk)
                
                # Get all recipients (deduplicated by email address)
                recipients = email.get_unique_recipient_emails()
                
                if not recipients:
                    messages.error(request, "No recipients selected for this email.")
                    return redirect('emails:detail', pk=email.pk)
                
                # Update email status
                email.status = 'QUEUED'
                email.save()
                
                # Record rate limit
                record_email_send()
                
                if send_now:
                    # Send immediately using sync wrapper
                    results = send_email_sync(email, recipients, smtp_config)
                    
                    # Update email status based on results
                    if results['failed'] == 0:
                        email.status = 'SENT'
                        email.sent_at = timezone.now()
                    else:
                        email.status = 'FAILED'
                        email.error_message = "; ".join(results['errors'])
                    
                    email.save()
                    
                    # Create queue entries for tracking
                    for recipient in recipients:
                        if isinstance(recipient, Recipient):
                            to_email = recipient.email
                            recipient_obj = recipient
                        else:
                            to_email = recipient
                            recipient_obj = None
                        
                        status = 'SENT' if results['failed'] == 0 else 'FAILED'
                        error_msg = None if results['failed'] == 0 else results['errors'][0] if results['errors'] else "Unknown error"
                        
                        EmailQueue.objects.create(
                            email=email,
                            recipient=recipient_obj,
                            to_email=to_email,
                            status=status,
                            error_message=error_msg,
                            sent_at=timezone.now() if status == 'SENT' else None
                        )
                    
                    if results['failed'] == 0:
                        messages.success(request, f"Email sent successfully to {results['success']} recipients!")
                    else:
                        messages.warning(request, f"Email sent with {results['failed']} failures: {', '.join(results['errors'][:3])}")
                else:
                    # Queue for later processing
                    for recipient in recipients:
                        if isinstance(recipient, Recipient):
                            to_email = recipient.email
                            recipient_obj = recipient
                        else:
                            to_email = recipient
                            recipient_obj = None
                        
                        EmailQueue.objects.create(
                            email=email,
                            recipient=recipient_obj,
                            to_email=to_email,
                            status='PENDING'
                        )
                    
                    messages.success(request, f"Email queued for sending to {len(recipients)} recipients.")
                
                return redirect('emails:detail', pk=email.pk)
                
            except Exception as e:
                logger.error(f"Error sending email {email.pk}: {str(e)}")
                email.status = 'FAILED'
                email.error_message = str(e)
                email.save()
                messages.error(request, f"Failed to send email: {str(e)}")
        else:
            # Form not valid, show form with errors
            form = EmailSendForm()
    else:
        form = EmailSendForm()
    
    context = {
        'email': email,
        'form': form,
        'title': f"Send Email: {email.subject}",
    }
    
    return render(request, 'emails/email_send.html', context)


# Async email processing view
def process_queue_view(request):
    """View to manually process the email queue."""
    if not is_manager(request.user):
        return HttpResponseForbidden("You need manager permissions to process the queue.")
    
    if request.method == 'POST':
        try:
            # Get all queued emails
            queued_emails = Email.objects.filter(status='QUEUED')
            
            processed_count = 0
            success_count = 0
            failed_count = 0
            
            for email in queued_emails:
                try:
                    # Process this email's queue
                    results = send_email_sync(
                        email, 
                        email.get_unique_recipient_emails(),
                        email.smtp_config
                    )
                    
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
                    
                except Exception as e:
                    logger.error(f"Error processing email {email.pk}: {str(e)}")
                    email.status = 'FAILED'
                    email.error_message = str(e)
                    email.save()
                    failed_count += 1
            
            messages.success(request, 
                f"Processed {processed_count} emails: {success_count} sent, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error processing queue: {str(e)}")
            messages.error(request, f"Error processing queue: {str(e)}")
    
    return redirect('emails:list')


# Retry failed emails view
def retry_failed_view(request):
    """View to retry failed emails."""
    if not is_manager(request.user):
        return HttpResponseForbidden("You need manager permissions to retry failed emails.")
    
    if request.method == 'POST':
        try:
            # Get all failed queue entries that can be retried
            retryable_entries = EmailQueue.objects.filter(
                status='FAILED',
                attempts__lt=2
            )
            
            retried_count = 0
            failed_count = 0
            
            for entry in retryable_entries:
                try:
                    email = entry.email
                    smtp_config = email.smtp_config
                    
                    if not smtp_config:
                        for mailing_list in email.mailing_lists.all():
                            if mailing_list.smtp_config:
                                smtp_config = mailing_list.smtp_config
                                break
                    
                    if not smtp_config:
                        entry.error_message = "No SMTP configuration available"
                        entry.save()
                        failed_count += 1
                        continue
                    
                    # Reset status for retry
                    entry.status = 'PENDING'
                    entry.save()
                    
                    # Send the email
                    results = send_email_sync(
                        email,
                        [entry.to_email],
                        smtp_config
                    )
                    
                    if results['failed'] == 0:
                        entry.mark_as_sent()
                        retried_count += 1
                    else:
                        entry.mark_as_failed(results['errors'][0] if results['errors'] else "Unknown error")
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error retrying queue entry {entry.pk}: {str(e)}")
                    entry.mark_as_failed(str(e))
                    failed_count += 1
            
            messages.success(request, 
                f"Retried {retried_count + failed_count} emails: {retried_count} successful, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error retrying failed emails: {str(e)}")
            messages.error(request, f"Error retrying failed emails: {str(e)}")
    
    return redirect('emails:list')


# Email Attachment Views
class EmailAttachmentCreateView(LoginRequiredMixin, CreateView):
    """Upload an attachment to an email."""
    
    model = EmailAttachment
    form_class = EmailAttachmentForm
    template_name = 'emails/attachment_form.html'
    
    def get_email(self):
        """Get the email for this attachment."""
        email_pk = self.kwargs.get('email_pk')
        return get_object_or_404(Email, pk=email_pk)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['email'] = self.get_email()
        return kwargs
    
    def form_valid(self, form):
        email = self.get_email()
        
        # Check access to email
        if not user_has_email_access(self.request.user, email):
            return HttpResponseForbidden("You don't have permission to add attachments to this email.")
        
        # Check if email is still a draft
        if email.status != 'DRAFT':
            messages.error(self.request, "You can only add attachments to draft emails.")
            return redirect('emails:detail', pk=email.pk)
        
        form.instance.email = email
        return super().form_valid(form)
    
    def get_success_url(self):
        email = self.get_email()
        return reverse('emails:detail', kwargs={'pk': email.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email'] = self.get_email()
        context['title'] = f"Add Attachment to {context['email'].subject}"
        return context


class EmailAttachmentDeleteView(LoginRequiredMixin, DeleteView):
    """Delete an email attachment."""
    
    model = EmailAttachment
    template_name = 'emails/attachment_confirm_delete.html'
    
    def get_success_url(self):
        attachment = self.object
        return reverse('emails:detail', kwargs={'pk': attachment.email.pk})
    
    def get_queryset(self):
        """Only allow deletion of attachments from accessible emails."""
        user = self.request.user
        
        if is_admin(user):
            return EmailAttachment.objects.all()
        
        # Get attachments from accessible emails
        accessible_emails = get_accessible_emails(user)
        return EmailAttachment.objects.filter(email__in=accessible_emails)


# Email Log Views
class EmailLogListView(ManagerRequiredMixin, ListView):
    """List email logs for debugging."""
    
    model = EmailLog
    template_name = 'emails/log_list.html'
    context_object_name = 'logs'
    paginate_by = 50
    
    def get_queryset(self):
        """Get logs, optionally filtered by email."""
        queryset = EmailLog.objects.all().order_by('-created_at')
        
        email_pk = self.kwargs.get('email_pk')
        if email_pk:
            email = get_object_or_404(Email, pk=email_pk)
            
            # Check access to email
            if not user_has_email_access(self.request.user, email):
                return EmailLog.objects.none()
            
            queryset = queryset.filter(email=email)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Email Logs'
        
        email_pk = self.kwargs.get('email_pk')
        if email_pk:
            context['email'] = get_object_or_404(Email, pk=email_pk)
        
        return context


# Queue Management Views
class EmailQueueListView(ManagerRequiredMixin, ListView):
    """List all email queue entries."""
    
    model = EmailQueue
    template_name = 'emails/queue_list.html'
    context_object_name = 'queue_entries'
    paginate_by = 50
    
    def get_queryset(self):
        """Get queue entries, optionally filtered."""
        queryset = EmailQueue.objects.all().order_by('-priority', 'created_at')
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        email_pk = self.request.GET.get('email')
        if email_pk:
            queryset = queryset.filter(email_id=email_pk)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Email Queue'
        context['status_choices'] = EmailQueue.STATUS_CHOICES
        return context


# AJAX Views for real-time queue processing
def queue_status_view(request):
    """AJAX view to get queue status."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    if not is_manager(request.user):
        return JsonResponse({'error': 'Manager permissions required'}, status=403)
    
    try:
        # Get queue statistics
        total_pending = EmailQueue.objects.filter(status='PENDING').count()
        total_sending = EmailQueue.objects.filter(status='SENDING').count()
        total_sent = EmailQueue.objects.filter(status='SENT').count()
        total_failed = EmailQueue.objects.filter(status='FAILED').count()
        total_retrying = EmailQueue.objects.filter(status='RETRYING').count()
        
        # Get recent activity
        recent_entries = EmailQueue.objects.all().order_by('-created_at')[:10]
        recent_data = []
        for entry in recent_entries:
            recent_data.append({
                'id': entry.id,
                'email_subject': entry.email.subject[:50] if entry.email else 'Unknown',
                'to_email': entry.to_email,
                'status': entry.status,
                'created_at': entry.created_at.isoformat() if entry.created_at else None
            })
        
        data = {
            'success': True,
            'stats': {
                'pending': total_pending,
                'sending': total_sending,
                'sent': total_sent,
                'failed': total_failed,
                'retrying': total_retrying,
                'total': total_pending + total_sending + total_sent + total_failed + total_retrying
            },
            'recent_activity': recent_data
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Error in queue_status_view: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# Dashboard view for email statistics
def email_dashboard_view(request):
    """Dashboard view showing email statistics."""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    
    # Get accessible emails
    emails = get_accessible_emails(request.user)
    
    # Calculate statistics
    total_emails = emails.count()
    draft_count = emails.filter(status='DRAFT').count()
    queued_count = emails.filter(status='QUEUED').count()
    sending_count = emails.filter(status='SENDING').count()
    sent_count = emails.filter(status='SENT').count()
    failed_count = emails.filter(status='FAILED').count()
    retrying_count = emails.filter(status='RETRYING').count()
    
    # Recent emails
    recent_emails = emails.order_by('-created_at')[:5]
    
    # Queue statistics
    total_queue_entries = EmailQueue.objects.count()
    pending_queue = EmailQueue.objects.filter(status='PENDING').count()
    
    # Log statistics
    error_logs = EmailLog.objects.filter(log_level='ERROR').count()
    warning_logs = EmailLog.objects.filter(log_level='WARNING').count()
    
    context = {
        'title': 'Email Dashboard',
        'stats': {
            'total_emails': total_emails,
            'draft': draft_count,
            'queued': queued_count,
            'sending': sending_count,
            'sent': sent_count,
            'failed': failed_count,
            'retrying': retrying_count,
            'total_queue': total_queue_entries,
            'pending_queue': pending_queue,
            'error_logs': error_logs,
            'warning_logs': warning_logs,
        },
        'recent_emails': recent_emails,
        'is_manager': is_manager(request.user),
        'is_admin': is_admin(request.user),
    }
    
    return render(request, 'emails/dashboard.html', context)
