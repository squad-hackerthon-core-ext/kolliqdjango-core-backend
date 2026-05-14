# permissions.py
from django.conf import settings
from rest_framework.permissions import BasePermission, IsAuthenticated
from apps.users.models import User  

class IsAuthenticatedOrInternalSecret(BasePermission):
    def has_permission(self, request, view):
        secret = request.headers.get('X-Internal-Secret')
        if secret and secret == settings.SECRET_KEY:
            return True
        return bool(request.user and request.user.is_authenticated)


def resolve_user(request):
    """
    For internal Node calls: look up user by ?phone= query param.
    For normal JWT calls: return request.user directly.
    Returns (user, error_response) — if error_response is not None, return it immediately.
    """
    from kolliq.utils import error_response

    secret = request.headers.get('X-Internal-Secret')
    if secret and secret == settings.SECRET_KEY:
        phone = request.query_params.get('phone') or request.data.get('phone')
        if not phone:
            return None, error_response('phone is required for internal calls', status=400)
        try:
            return User.objects.get(phone=phone), None
        except User.DoesNotExist:
            return None, error_response('User not found', status=404)

    return request.user, None