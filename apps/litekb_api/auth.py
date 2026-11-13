from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.views import APIView, exception_handler

from common.exception.app_exception import AppApiException

from .models import ServiceClient


class ServiceAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != b"bearer":
            raise AuthenticationFailed("A LiteKB service key is required.")
        try:
            key = parts[1].decode("ascii")
        except UnicodeError:
            raise AuthenticationFailed("Invalid service key.")
        if not key.startswith("lk_") or len(key) != 46:
            raise AuthenticationFailed("Invalid service key.")
        client = ServiceClient.objects.select_related("project__owner").filter(
            key_hash=ServiceClient.digest(key), is_active=True, project__owner__is_active=True
        ).first()
        if client is None:
            raise AuthenticationFailed("Invalid service key.")
        return client.project.owner, client

    def authenticate_header(self, request):
        return "Bearer"


class HasServiceClient(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, ServiceClient)


class ServiceAPIView(APIView):
    authentication_classes = [ServiceAuthentication]
    permission_classes = [HasServiceClient]

    def get_exception_handler(self):
        # Internal admin endpoints use a legacy envelope. Product APIs use HTTP status codes.
        return exception_handler

    def handle_exception(self, exc):
        if isinstance(exc, AppApiException):
            exc = ValidationError(str(exc.message))
        return super().handle_exception(exc)
