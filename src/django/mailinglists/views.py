# MailingLists app views
# AD-002: django-guardian for object-level permissions

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import Http404
from guardian.mixins import PermissionRequiredMixin
from guardian.decorators import permission_required
from .models import MailingList, SmtpConfig
from .forms import MailingListForm, SmtpConfigForm, MailingListAccessForm
from accounts.utils import is_admin, is_manager, get_user_role, ADMIN_GROUP, MANAGER_GROUP


class MailingListListView(LoginRequiredMixin, ListView):
    """
    List all mailing lists that the user has access to.
    
    - ADMIN: Can see all mailing lists
    - MANAGER: Can see mailing lists they have access to
    - USER: Can see mailing lists they have access to
    """
    model = MailingList
    template_name = 'mailinglists/list.html'
    context_object_name = 'mailinglists'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter mailing lists based on user permissions."""
        queryset = super().get_queryset().order_by('name')
        
        # ADMIN can see all mailing lists
        if is_admin(self.request.user):
            return queryset
        
        # MANAGER and USER can only see mailing lists they have access to
        # This includes lists where they are in users_with_access or have object permissions
        user = self.request.user
        
        # Get lists where user is in users_with_access
        accessible_lists = MailingList.objects.filter(users_with_access=user)
        
        # Also get lists where user has any object permission
        from guardian.models import UserObjectPermission
        permission_content_type = self.model._meta.app_label + '.' + self.model._meta.model_name
        
        # Get object IDs where user has permissions
        permission_ids = UserObjectPermission.objects.filter(
            user=user,
            permission__content_type__app_label='mailinglists',
            permission__codename__in=['view_mailinglist', 'change_mailinglist', 'delete_mailinglist']
        ).values_list('object_pk', flat=True)
        
        permission_lists = MailingList.objects.filter(pk__in=permission_ids)
        
        # Combine both querysets
        return accessible_lists.union(permission_lists).order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_role'] = get_user_role(self.request.user)
        context['is_admin'] = is_admin(self.request.user)
        context['is_manager'] = is_manager(self.request.user)
        return context


class MailingListCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Create a new mailing list.
    
    - ADMIN: Can create mailing lists
    - MANAGER: Can create mailing lists
    - USER: Cannot create mailing lists
    """
    model = MailingList
    form_class = MailingListForm
    template_name = 'mailinglists/form.html'
    success_url = reverse_lazy('mailinglists:list')
    
    def test_func(self):
        """Only ADMIN and MANAGER can create mailing lists."""
        return is_manager(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to create mailing lists.")
        return redirect('mailinglists:list')
    
    def get_form_kwargs(self):
        """Add request to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        """Set the created_by field to the current user."""
        form.instance.created_by = self.request.user
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Create'
        return context


class MailingListUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Update an existing mailing list.
    
    - ADMIN: Can edit any mailing list
    - MANAGER: Can edit mailing lists they have access to
    - USER: Cannot edit mailing lists
    """
    model = MailingList
    form_class = MailingListForm
    template_name = 'mailinglists/form.html'
    success_url = reverse_lazy('mailinglists:list')
    
    def test_func(self):
        """Check if user can edit this mailing list."""
        mailing_list = self.get_object()
        
        # ADMIN can edit any mailing list
        if is_admin(self.request.user):
            return True
        
        # MANAGER can edit mailing lists they have access to
        if is_manager(self.request.user):
            # Check if user has change permission or is in users_with_access
            return (
                self.request.user.has_perm('change_mailinglist', mailing_list) or
                mailing_list.users_with_access.filter(pk=self.request.user.pk).exists()
            )
        
        # USER cannot edit mailing lists
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to edit this mailing list.")
        return redirect('mailinglists:list')
    
    def get_form_kwargs(self):
        """Add request to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Edit'
        return context


class MailingListDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    View details of a mailing list.
    
    - ADMIN: Can view any mailing list
    - MANAGER: Can view mailing lists they have access to
    - USER: Can view mailing lists they have access to
    """
    model = MailingList
    template_name = 'mailinglists/detail.html'
    context_object_name = 'mailinglist'
    
    def test_func(self):
        """Check if user can view this mailing list."""
        mailing_list = self.get_object()
        
        # ADMIN can view any mailing list
        if is_admin(self.request.user):
            return True
        
        # Check if user has view permission or is in users_with_access
        return (
            self.request.user.has_perm('view_mailinglist', mailing_list) or
            mailing_list.users_with_access.filter(pk=self.request.user.pk).exists()
        )
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to view this mailing list.")
        return redirect('mailinglists:list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mailing_list = self.get_object()
        
        # Add SMTP config if it exists
        context['smtp_config'] = mailing_list.smtp_config.first()
        context['is_admin'] = is_admin(self.request.user)
        context['is_manager'] = is_manager(self.request.user)
        context['user_role'] = get_user_role(self.request.user)
        
        # Check if user can edit this mailing list
        context['can_edit'] = (
            is_admin(self.request.user) or
            (is_manager(self.request.user) and (
                self.request.user.has_perm('change_mailinglist', mailing_list) or
                mailing_list.users_with_access.filter(pk=self.request.user.pk).exists()
            ))
        )
        
        # Check if user can manage SMTP config
        context['can_manage_smtp'] = context['can_edit']
        
        return context


class MailingListDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    Delete a mailing list.
    
    - ADMIN: Can delete any mailing list
    - MANAGER: Can delete mailing lists they have access to
    - USER: Cannot delete mailing lists
    """
    model = MailingList
    template_name = 'mailinglists/confirm_delete.html'
    success_url = reverse_lazy('mailinglists:list')
    context_object_name = 'mailinglist'
    
    def test_func(self):
        """Check if user can delete this mailing list."""
        mailing_list = self.get_object()
        
        # ADMIN can delete any mailing list
        if is_admin(self.request.user):
            return True
        
        # MANAGER can delete mailing lists they have access to
        if is_manager(self.request.user):
            return (
                self.request.user.has_perm('delete_mailinglist', mailing_list) or
                mailing_list.users_with_access.filter(pk=self.request.user.pk).exists()
            )
        
        # USER cannot delete mailing lists
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to delete this mailing list.")
        return redirect('mailinglists:list')
    
    def delete(self, request, *args, **kwargs):
        """Delete the mailing list and show success message."""
        mailing_list = self.get_object()
        messages.success(request, f"Mailing list '{mailing_list.name}' deleted successfully!")
        return super().delete(request, *args, **kwargs)


class SmtpConfigCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Create SMTP configuration for a mailing list.
    
    - ADMIN: Can create SMTP config for any mailing list
    - MANAGER: Can create SMTP config for mailing lists they have access to
    - USER: Cannot create SMTP config
    """
    model = SmtpConfig
    form_class = SmtpConfigForm
    template_name = 'mailinglists/smtp_form.html'
    
    def test_func(self):
        """Check if user can create SMTP config for this mailing list."""
        mailing_list = get_object_or_404(MailingList, pk=self.kwargs.get('mailinglist_pk'))
        
        # ADMIN can create SMTP config for any mailing list
        if is_admin(self.request.user):
            return True
        
        # MANAGER can create SMTP config for mailing lists they have access to
        if is_manager(self.request.user):
            return (
                self.request.user.has_perm('change_mailinglist', mailing_list) or
                mailing_list.users_with_access.filter(pk=self.request.user.pk).exists()
            )
        
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to configure SMTP for this mailing list.")
        return redirect('mailinglists:list')
    
    def get_form_kwargs(self):
        """Add request to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        """Set the mailing_list field."""
        mailing_list = get_object_or_404(MailingList, pk=self.kwargs.get('mailinglist_pk'))
        form.instance.mailing_list = mailing_list
        return super().form_valid(form)
    
    def get_success_url(self):
        """Redirect to mailing list detail after creation."""
        mailing_list = get_object_or_404(MailingList, pk=self.kwargs.get('mailinglist_pk'))
        return reverse('mailinglists:detail', kwargs={'pk': mailing_list.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mailing_list = get_object_or_404(MailingList, pk=self.kwargs.get('mailinglist_pk'))
        context['mailinglist'] = mailing_list
        context['action'] = 'Create SMTP Configuration'
        return context


class SmtpConfigUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Update SMTP configuration for a mailing list.
    
    - ADMIN: Can update SMTP config for any mailing list
    - MANAGER: Can update SMTP config for mailing lists they have access to
    - USER: Cannot update SMTP config
    """
    model = SmtpConfig
    form_class = SmtpConfigForm
    template_name = 'mailinglists/smtp_form.html'
    
    def test_func(self):
        """Check if user can update SMTP config for this mailing list."""
        smtp_config = self.get_object()
        mailing_list = smtp_config.mailing_list
        
        # ADMIN can update SMTP config for any mailing list
        if is_admin(self.request.user):
            return True
        
        # MANAGER can update SMTP config for mailing lists they have access to
        if is_manager(self.request.user):
            return (
                self.request.user.has_perm('change_mailinglist', mailing_list) or
                mailing_list.users_with_access.filter(pk=self.request.user.pk).exists()
            )
        
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to update SMTP configuration for this mailing list.")
        return redirect('mailinglists:list')
    
    def get_form_kwargs(self):
        """Add request to form kwargs."""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def get_success_url(self):
        """Redirect to mailing list detail after update."""
        smtp_config = self.get_object()
        return reverse('mailinglists:detail', kwargs={'pk': smtp_config.mailing_list.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        smtp_config = self.get_object()
        context['mailinglist'] = smtp_config.mailing_list
        context['action'] = 'Update SMTP Configuration'
        return context


@login_required
@user_passes_test(lambda u: is_manager(u), login_url='mailinglists:list')
def manage_access_view(request, pk):
    """
    Manage user access to a mailing list.
    
    - ADMIN: Can manage access for any mailing list
    - MANAGER: Can manage access for mailing lists they have access to
    - USER: Cannot manage access
    """
    mailing_list = get_object_or_404(MailingList, pk=pk)
    
    # Check permissions
    if not is_admin(request.user):
        # For managers, check if they have access to this mailing list
        if not (request.user.has_perm('change_mailinglist', mailing_list) or
                mailing_list.users_with_access.filter(pk=request.user.pk).exists()):
            messages.error(request, "You do not have permission to manage access for this mailing list.")
            return redirect('mailinglists:list')
    
    if request.method == 'POST':
        form = MailingListAccessForm(request.POST, mailing_list=mailing_list, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "Mailing list access updated successfully!")
            return redirect('mailinglists:detail', pk=mailing_list.pk)
    else:
        form = MailingListAccessForm(mailing_list=mailing_list, request=request)
    
    return render(request, 'mailinglists/access_form.html', {
        'form': form,
        'mailinglist': mailing_list,
        'is_admin': is_admin(request.user),
        'is_manager': is_manager(request.user),
    })


# Function-based views for permission-required actions
@login_required
def mailinglist_access_check(request, pk):
    """Check if user has access to a mailing list."""
    mailing_list = get_object_or_404(MailingList, pk=pk)
    
    # ADMIN can access any mailing list
    if is_admin(request.user):
        return True
    
    # Check if user has view permission or is in users_with_access
    return (
        request.user.has_perm('view_mailinglist', mailing_list) or
        mailing_list.users_with_access.filter(pk=request.user.pk).exists()
    )