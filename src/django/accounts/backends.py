from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend that allows login with either email or username.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        
        # Try to authenticate with username first
        try:
            user = super().authenticate(request, username=username, password=password, **kwargs)
            if user is not None:
                return user
        except UserModel.DoesNotExist:
            pass
        
        # If username authentication fails, try with email
        if username and '@' in username:
            try:
                user = UserModel.objects.get(email=username)
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user
            except UserModel.DoesNotExist:
                return None
        else:
            # If it doesn't look like an email, try as username again
            try:
                user = UserModel.objects.get(username=username)
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user
            except UserModel.DoesNotExist:
                return None
        
        return None