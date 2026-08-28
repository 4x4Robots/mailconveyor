from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .forms import CustomUserCreationForm, CustomUserChangeForm, CustomAuthenticationForm, ProfileUpdateForm
from .utils import ADMIN_GROUP, MANAGER_GROUP, USER_GROUP, is_admin, is_manager, get_user_role, assign_role_to_user


def login_view(request):
    """User login view."""
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('accounts:user_list')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """User logout view."""
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('accounts:login')


class UserListView(LoginRequiredMixin, ListView):
    """List all users with filtering by role."""
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().order_by('username')
        
        # Filter by role if specified
        role_filter = self.request.GET.get('role')
        if role_filter and role_filter in [ADMIN_GROUP, MANAGER_GROUP, USER_GROUP]:
            queryset = queryset.filter(groups__name=role_filter)
        
        # ADMIN can see all users
        if is_admin(self.request.user):
            return queryset
        
        # MANAGER can see all users but not edit them
        elif is_manager(self.request.user):
            return queryset
        
        # Regular USER can only see themselves
        else:
            return queryset.filter(pk=self.request.user.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = [(USER_GROUP, 'User'), (MANAGER_GROUP, 'Manager'), (ADMIN_GROUP, 'Admin')]
        context['current_role_filter'] = self.request.GET.get('role', '')
        return context


class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create new user (ADMIN only)."""
    model = User
    form_class = CustomUserCreationForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to create users.")
        return redirect('accounts:user_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Set role based on form data
        role = form.cleaned_data.get('role')
        user = self.object
        assign_role_to_user(user, role)
        
        messages.success(self.request, f"User {user.username} created successfully!")
        return response


class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update user (ADMIN can edit all, others can edit self)."""
    model = User
    form_class = CustomUserChangeForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')
    
    def test_func(self):
        user = self.get_object()
        # ADMIN can edit anyone
        if is_admin(self.request.user):
            return True
        # Others can only edit themselves
        return user == self.request.user
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to edit this user.")
        return redirect('accounts:user_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Update role based on form data (ADMIN only)
        if is_admin(self.request.user):
            role = form.cleaned_data.get('role')
            assign_role_to_user(self.object, role)
        
        messages.success(self.request, f"User {self.object.username} updated successfully!")
        return response
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Set initial role for the form
        user = self.get_object()
        if user.groups.exists():
            kwargs['initial'] = kwargs.get('initial', {})
            kwargs['initial']['role'] = user.groups.first().name
        return kwargs


class UserDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete user (ADMIN only)."""
    model = User
    template_name = 'accounts/user_confirm_delete.html'
    success_url = reverse_lazy('accounts:user_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to delete users.")
        return redirect('accounts:user_list')
    
    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        if user == request.user:
            messages.error(request, "You cannot delete your own account.")
            return redirect('accounts:user_list')
        messages.success(request, f"User {user.username} deleted successfully!")
        return super().delete(request, *args, **kwargs)


@login_required
def profile_view(request):
    """View and edit own profile."""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated!")
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def change_password_view(request):
    """Change own password."""
    from django.contrib.auth.forms import PasswordChangeForm
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Re-authenticate user to prevent logout
            login(request, user)
            messages.success(request, "Your password has been changed!")
            return redirect('accounts:profile')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})