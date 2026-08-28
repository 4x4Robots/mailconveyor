# MailingLists app signals
# AD-002: django-guardian for object-level permissions

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.models import User
from guardian.shortcuts import assign_perm
from .models import MailingList


@receiver(post_save, sender=MailingList)
def assign_creator_permissions(sender, instance, created, **kwargs):
    """
    Assign object-level permissions to the creator when a mailing list is created.
    
    The creator gets full permissions on the mailing list they created.
    """
    if created and instance.created_by:
        # Assign all permissions to the creator
        user = instance.created_by
        
        # Assign view, change, and delete permissions
        assign_perm('view_mailinglist', user, instance)
        assign_perm('change_mailinglist', user, instance)
        assign_perm('delete_mailinglist', user, instance)
        
        # Also add to users_with_access if not already there
        if user not in instance.users_with_access.all():
            instance.users_with_access.add(user)


@receiver(m2m_changed, sender=MailingList.users_with_access.through)
def assign_access_permissions(sender, instance, action, pk_set, **kwargs):
    """
    Assign view permission to users when they are added to users_with_access.
    
    When users are added to the mailing list's users_with_access,
    they automatically get view permission.
    """
    if action == 'post_add' and pk_set:
        # Get the users that were added
        users = User.objects.filter(pk__in=pk_set)
        for user in users:
            assign_perm('view_mailinglist', user, instance)
    
    elif action == 'post_remove' and pk_set:
        # When users are removed, remove their permissions
        users = User.objects.filter(pk__in=pk_set)
        for user in users:
            # Remove all mailing list permissions for this user on this list
            from guardian.models import UserObjectPermission
            UserObjectPermission.objects.filter(
                user=user,
                object_pk=instance.pk,
                permission__content_type__app_label='mailinglists',
                permission__codename__in=['view_mailinglist', 'change_mailinglist', 'delete_mailinglist']
            ).delete()


@receiver(post_save, sender=MailingList)
def assign_admin_permissions(sender, instance, created, **kwargs):
    """
    Assign permissions to Admin users for all mailing lists.
    
    Admin users should have full access to all mailing lists.
    """
    if created:
        from accounts.utils import ADMIN_GROUP, is_admin
        from django.contrib.auth.models import Group
        
        # Get all admin users
        admin_group = Group.objects.filter(name=ADMIN_GROUP).first()
        if admin_group:
            admin_users = admin_group.user_set.all()
            for user in admin_users:
                assign_perm('view_mailinglist', user, instance)
                assign_perm('change_mailinglist', user, instance)
                assign_perm('delete_mailinglist', user, instance)
                if user not in instance.users_with_access.all():
                    instance.users_with_access.add(user)