"""Core app views.

Contains:
- health: Health check endpoint
- LoginView: JWT token obtain with user/role info
- RefreshView: JWT token refresh
- MeView: Current authenticated user info
"""

from django.db import connection
from django.http import JsonResponse

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken

from praxi_backend.core.serializers import (
    LoginSerializer,
    RefreshSerializer,
    RoleSerializer,
    UserMeSerializer,
)


def health(request):
    """Health check endpoint - no authentication required."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1;')
    except Exception as exc:
        return JsonResponse({'status': 'error', 'detail': str(exc)}, status=503)

    return JsonResponse({'status': 'ok'})


class LoginView(APIView):
    """Obtain JWT access and refresh tokens.

    POST /api/auth/login/
    Body: {"username": "...", "password": "..."}
    Returns: {"user": {...}, "access": "...", "refresh": "..."}
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        # Add role to token claims
        role = getattr(user, 'role', None)
        if role:
            refresh['role'] = role.name
        else:
            refresh['role'] = None

        access = refresh.access_token

        # Build user response with role
        role_data = None
        if role:
            role_data = RoleSerializer(role).data

        return Response(
            {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': role_data,
                },
                'access': str(access),
                'refresh': str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class RefreshView(APIView):
    """Refresh JWT access token.

    POST /api/auth/refresh/
    Body: {"refresh": "..."}
    Returns: {"access": "..."}
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from rest_framework_simplejwt.tokens import RefreshToken

        refresh_token = serializer.validated_data['refresh']
        refresh = RefreshToken(refresh_token)
        access = refresh.access_token

        return Response(
            {
                'access': str(access),
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """Get current authenticated user info.

    GET /api/auth/me/
    Returns: {"id": ..., "username": "...", "email": "...", "role": {...}}
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Legacy function-based view for backwards compatibility
from rest_framework.decorators import api_view, permission_classes as perm_classes


@api_view(['GET'])
@perm_classes([IsAuthenticated])
def me(request):
    """Legacy /auth/me/ endpoint - use MeView instead."""
    user = request.user
    role_payload = None
    if getattr(user, 'role_id', None):
        role_payload = {
            'name': user.role.name,
            'label': user.role.label,
        }

    return Response(
        {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': role_payload,
        }
    )
