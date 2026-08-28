from .models import CustomUser


def user_role(request):
    """
    Context processor to add user role information to templates.
    """
    if request.user.is_authenticated:
        return {
            'user_role': request.user.get_role(),
            'is_admin': request.user.is_admin(),
            'is_manager': request.user.is_manager(),
            'is_user': request.user.is_user(),
        }
    return {
        'user_role': None,
        'is_admin': False,
        'is_manager': False,
        'is_user': False,
    }