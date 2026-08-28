# Recipients app views
# AD-002: django-guardian for object-level permissions
# AD-005: Recipient uniqueness by (first_name, last_name, email), deduplicate emails by address
# AD-006: Users and Recipients are separate models

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.db.models import Q
import csv
from io import TextIOWrapper, StringIO

from .models import Recipient, RecipientImportLog
from .forms import RecipientForm, RecipientSearchForm, CSVImportForm
from mailinglists.models import MailingList
from django.contrib.auth.models import User


def is_admin(user):
    """Check if user is an admin."""
    return user.is_authenticated and user.is_app_admin


def is_manager(user):
    """Check if user is a manager or admin."""
    return user.is_authenticated and user.is_app_manager


def get_accessible_mailing_lists(user):
    """Get mailing lists that the user has access to."""
    if user.is_app_admin:
        return MailingList.objects.all()
    elif user.is_authenticated:
        return MailingList.objects.filter(
            Q(users_with_access=user) | Q(created_by=user)
        ).distinct()
    return MailingList.objects.none()


def get_accessible_recipients(user):
    """Get recipients that the user has access to (via accessible mailing lists)."""
    accessible_lists = get_accessible_mailing_lists(user)
    return Recipient.objects.filter(mailing_lists__in=accessible_lists).distinct()


class RecipientListView(LoginRequiredMixin, ListView):
    """
    List all recipients that the user has access to.
    """
    model = Recipient
    template_name = 'recipients/recipient_list.html'
    context_object_name = 'recipients'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter recipients by user access."""
        queryset = super().get_queryset()
        
        # Get search query
        search_query = self.request.GET.get('search_query', '')
        mailing_list_id = self.request.GET.get('mailing_list', '')
        
        # Filter by accessible mailing lists
        accessible_lists = get_accessible_mailing_lists(self.request.user)
        queryset = queryset.filter(mailing_lists__in=accessible_lists).distinct()
        
        # Apply search filter
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(get_full_name__icontains=search_query)
            )
        
        # Apply mailing list filter
        if mailing_list_id:
            try:
                mailing_list = MailingList.objects.get(pk=mailing_list_id)
                # Check if user has access to this mailing list
                if mailing_list in accessible_lists:
                    queryset = queryset.filter(mailing_lists=mailing_list)
            except MailingList.DoesNotExist:
                pass
        
        return queryset.order_by('last_name', 'first_name', 'email')
    
    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        
        # Add search form
        context['search_form'] = RecipientSearchForm(
            self.request.GET,
            user=self.request.user
        )
        
        # Add accessible mailing lists for filter
        context['accessible_mailing_lists'] = get_accessible_mailing_lists(self.request.user)
        
        # Add user role info
        context['is_admin'] = self.request.user.is_app_admin
        context['is_manager'] = self.request.user.is_app_manager
        
        return context


class RecipientCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Create a new recipient.
    """
    model = Recipient
    form_class = RecipientForm
    template_name = 'recipients/recipient_form.html'
    
    def test_func(self):
        """Only managers and admins can create recipients."""
        return self.request.user.is_app_manager
    
    def handle_no_permission(self):
        """Redirect to recipient list with error message."""
        messages.error(self.request, "You don't have permission to create recipients.")
        return redirect('recipients:list')
    
    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Set the created_by field to the current user."""
        form.instance.created_by = self.request.user
        return super().form_valid(form)
    
    def get_success_url(self):
        """Redirect to recipient list after successful creation."""
        messages.success(self.request, "Recipient created successfully!")
        return reverse('recipients:list')
    
    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        context['is_create'] = True
        return context


class RecipientUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Update an existing recipient.
    """
    model = Recipient
    form_class = RecipientForm
    template_name = 'recipients/recipient_form.html'
    
    def test_func(self):
        """Check if user has permission to edit this recipient."""
        recipient = self.get_object()
        
        # Admins can edit all recipients
        if self.request.user.is_app_admin:
            return True
        
        # Managers can edit recipients they created or that are in mailing lists they manage
        if self.request.user.is_app_manager:
            # Check if recipient is in any mailing list the user has access to
            accessible_lists = get_accessible_mailing_lists(self.request.user)
            return recipient.mailing_lists.filter(pk__in=accessible_lists.values_list('pk', flat=True)).exists()
        
        # Regular users can only edit recipients they created
        return recipient.created_by == self.request.user
    
    def handle_no_permission(self):
        """Redirect to recipient list with error message."""
        messages.error(self.request, "You don't have permission to edit this recipient.")
        return redirect('recipients:list')
    
    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Update the updated_at field."""
        form.instance.updated_at = timezone.now()
        return super().form_valid(form)
    
    def get_success_url(self):
        """Redirect to recipient list after successful update."""
        messages.success(self.request, "Recipient updated successfully!")
        return reverse('recipients:list')
    
    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        context['is_create'] = False
        return context


class RecipientDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    View details of a specific recipient.
    """
    model = Recipient
    template_name = 'recipients/recipient_detail.html'
    
    def test_func(self):
        """Check if user has permission to view this recipient."""
        recipient = self.get_object()
        
        # Admins can view all recipients
        if self.request.user.is_app_admin:
            return True
        
        # Check if recipient is in any mailing list the user has access to
        accessible_lists = get_accessible_mailing_lists(self.request.user)
        return recipient.mailing_lists.filter(pk__in=accessible_lists.values_list('pk', flat=True)).exists()
    
    def handle_no_permission(self):
        """Redirect to recipient list with error message."""
        messages.error(self.request, "You don't have permission to view this recipient.")
        return redirect('recipients:list')
    
    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        
        # Add user role info
        context['is_admin'] = self.request.user.is_app_admin
        context['is_manager'] = self.request.user.is_app_manager
        
        return context


class RecipientDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Delete a recipient.
    """
    model = Recipient
    template_name = 'recipients/recipient_confirm_delete.html'
    success_url = reverse_lazy('recipients:list')
    
    def test_func(self):
        """Check if user has permission to delete this recipient."""
        recipient = self.get_object()
        
        # Only admins can delete recipients
        return self.request.user.is_app_admin
    
    def handle_no_permission(self):
        """Redirect to recipient list with error message."""
        messages.error(self.request, "You don't have permission to delete recipients.")
        return redirect('recipients:list')
    
    def delete(self, request, *args, **kwargs):
        """Delete the recipient and show success message."""
        messages.success(self.request, "Recipient deleted successfully!")
        return super().delete(request, *args, **kwargs)


@login_required
@user_passes_test(is_manager, login_url='accounts:login')
def import_recipients_view(request):
    """
    Import recipients from a CSV file.
    
    Expected CSV format: first_name, last_name, email
    """
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES, user=request.user)
        
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            mailing_list_id = form.cleaned_data.get('mailing_list')
            
            try:
                # Create import log
                import_log = RecipientImportLog.objects.create(
                    file_name=csv_file.name,
                    uploaded_by=request.user,
                    status='PENDING'
                )
                
                # Read and decode the CSV file
                if hasattr(csv_file, 'read'):
                    # File was uploaded
                    file_content = csv_file.read().decode('utf-8')
                else:
                    # For testing, might be a string
                    file_content = str(csv_file)
                
                # Parse CSV
                csv_reader = csv.DictReader(StringIO(file_content))
                
                # Get the mailing list if specified
                mailing_list = None
                if mailing_list_id:
                    try:
                        mailing_list = MailingList.objects.get(pk=mailing_list_id)
                    except MailingList.DoesNotExist:
                        messages.error(request, f"Mailing list with ID {mailing_list_id} not found.")
                        return redirect('recipients:list')
                
                # Process each row
                imported_count = 0
                skipped_count = 0
                errors = []
                
                for row_num, row in enumerate(csv_reader, start=1):
                    try:
                        first_name = row.get('first_name', '').strip()
                        last_name = row.get('last_name', '').strip()
                        email = row.get('email', '').strip()
                        
                        # Validate required fields
                        if not first_name or not last_name or not email:
                            errors.append(f"Row {row_num}: Missing required fields (first_name, last_name, email)")
                            skipped_count += 1
                            continue
                        
                        # Validate email
                        validator = EmailValidator(message="Invalid email address")
                        try:
                            validator(email)
                        except ValidationError:
                            errors.append(f"Row {row_num}: Invalid email address '{email}'")
                            skipped_count += 1
                            continue
                        
                        # Check for duplicates (AD-005)
                        if Recipient.objects.filter(
                            first_name=first_name,
                            last_name=last_name,
                            email=email
                        ).exists():
                            errors.append(f"Row {row_num}: Duplicate recipient '{first_name} {last_name} <{email}>'")
                            skipped_count += 1
                            continue
                        
                        # Create the recipient
                        recipient = Recipient.objects.create(
                            first_name=first_name,
                            last_name=last_name,
                            email=email,
                            created_by=request.user
                        )
                        
                        # Add to mailing list if specified
                        if mailing_list:
                            recipient.mailing_lists.add(mailing_list)
                        
                        imported_count += 1
                        
                    except Exception as e:
                        errors.append(f"Row {row_num}: Error - {str(e)}")
                        skipped_count += 1
                
                # Update import log
                import_log.total_records = row_num
                import_log.successful_records = imported_count
                import_log.failed_records = skipped_count
                
                if errors:
                    import_log.error_message = "\n".join(errors[:10])  # Store first 10 errors
                    import_log.status = 'PARTIAL' if imported_count > 0 else 'FAILED'
                else:
                    import_log.status = 'SUCCESS'
                
                import_log.completed_at = timezone.now()
                import_log.save()
                
                # Show results to user
                if imported_count > 0:
                    messages.success(request, f"Successfully imported {imported_count} recipients.")
                if skipped_count > 0:
                    messages.warning(request, f"Skipped {skipped_count} recipients due to errors.")
                if errors:
                    messages.error(request, f"Encountered {len(errors)} errors during import.")
                
                return redirect('recipients:list')
                
            except Exception as e:
                # Update import log with error
                import_log.error_message = str(e)
                import_log.status = 'FAILED'
                import_log.completed_at = timezone.now()
                import_log.save()
                
                messages.error(request, f"Error importing recipients: {str(e)}")
                return redirect('recipients:list')
    else:
        form = CSVImportForm(user=request.user)
    
    return render(request, 'recipients/recipient_import.html', {
        'form': form,
        'is_admin': request.user.is_app_admin,
        'is_manager': request.user.is_app_manager,
    })


@login_required
def export_recipients_view(request):
    """
    Export recipients to a CSV file.
    """
    # Get accessible recipients
    accessible_lists = get_accessible_mailing_lists(request.user)
    recipients = Recipient.objects.filter(
        mailing_lists__in=accessible_lists
    ).distinct().order_by('last_name', 'first_name', 'email')
    
    # Get filter parameters
    mailing_list_id = request.GET.get('mailing_list', '')
    if mailing_list_id:
        try:
            mailing_list = MailingList.objects.get(pk=mailing_list_id)
            if mailing_list in accessible_lists:
                recipients = recipients.filter(mailing_lists=mailing_list)
        except MailingList.DoesNotExist:
            pass
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="recipients_export.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow(['First Name', 'Last Name', 'Email', 'Mailing Lists', 'Created At', 'Created By'])
    
    # Write data
    for recipient in recipients:
        mailing_lists = ', '.join([ml.name for ml in recipient.mailing_lists.all()])
        created_by = recipient.created_by.get_full_name() if recipient.created_by else ''
        writer.writerow([
            recipient.first_name,
            recipient.last_name,
            recipient.email,
            mailing_lists,
            recipient.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            created_by
        ])
    
    return response


@login_required
@user_passes_test(is_manager, login_url='accounts:login')
def manage_recipient_mailing_lists_view(request, pk):
    """
    Manage which mailing lists a recipient belongs to.
    """
    recipient = get_object_or_404(Recipient, pk=pk)
    
    # Check permissions
    if not request.user.is_app_admin:
        accessible_lists = get_accessible_mailing_lists(request.user)
        if not recipient.mailing_lists.filter(pk__in=accessible_lists.values_list('pk', flat=True)).exists():
            messages.error(request, "You don't have permission to manage this recipient.")
            return redirect('recipients:list')
    
    if request.method == 'POST':
        # Get selected mailing lists from form
        selected_lists = request.POST.getlist('mailing_lists')
        
        # Validate that user has access to all selected lists
        if not request.user.is_app_admin:
            accessible_list_ids = set(accessible_lists.values_list('pk', flat=True))
            for list_id in selected_lists:
                if int(list_id) not in accessible_list_ids:
                    messages.error(request, f"You don't have access to mailing list {list_id}.")
                    return redirect('recipients:manage_mailing_lists', pk=pk)
        
        # Update recipient's mailing lists
        recipient.mailing_lists.set(selected_lists)
        recipient.save()
        
        messages.success(request, "Recipient's mailing lists updated successfully!")
        return redirect('recipients:detail', pk=pk)
    
    # Get accessible mailing lists for the form
    if request.user.is_app_admin:
        all_mailing_lists = MailingList.objects.all()
    else:
        all_mailing_lists = accessible_lists
    
    return render(request, 'recipients/manage_mailing_lists.html', {
        'recipient': recipient,
        'all_mailing_lists': all_mailing_lists,
        'is_admin': request.user.is_app_admin,
        'is_manager': request.user.is_app_manager,
    })
