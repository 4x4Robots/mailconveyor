from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group


class CustomUserAdmin(UserAdmin):
    """Custom admin configuration for User model.
    
    - Uses username as email (validated to be email format)
    - Roles managed through groups (Admin, Manager, User)
    - Simplified field display
    """
    
    # Fields to be used in displaying the User model
    list_display = ('username', 'first_name', 'last_name', 'get_groups_display', 'is_active', 'date_joined', 'last_login')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name')
    ordering = ('username',)
    
    # Fields for the user creation form
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    # Fields for the user change form
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    def get_groups_display(self, obj):
        """Display the user's groups (roles) as a comma-separated list."""
        return ", ".join([g.name for g in obj.groups.all()])
    
    get_groups_display.short_description = 'Roles'


class GroupAdmin(admin.ModelAdmin):
    """Admin configuration for groups (roles)."""
    list_display = ('name',)
    ordering = ('name',)


# Unregister the default User and Group admin and register our custom ones
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Also customize the Group admin
admin.site.unregister(Group)
admin.site.register(Group, GroupAdmin)