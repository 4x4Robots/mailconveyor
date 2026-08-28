from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    """Custom admin configuration for CustomUser model."""
    
    # The forms to add and change user instances
    form = UserChangeForm
    add_form = UserCreationForm
    
    # Fields to be used in displaying the User model
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined', 'last_login')
    list_filter = ('role', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('email',)
    
    # Fields for the user creation form
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )
    
    # Fields for the user change form
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions', 'role'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )


# Register the CustomUser model with the custom admin class
admin.site.register(CustomUser, CustomUserAdmin)