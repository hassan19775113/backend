"""Serializers for the core app.

Contains serializers for User, Role, and AuditLog models.
Follows the Read/Write serializer pattern per architecture rules.
"""

from rest_framework import serializers

from praxi_backend.core.models import AuditLog, Role, User


# -----------------------------------------------------------------------------
# Role Serializers
# -----------------------------------------------------------------------------


class RoleSerializer(serializers.ModelSerializer):
    """Read-only serializer for Role model."""

    class Meta:
        model = Role
        fields = ['id', 'name', 'label']
        read_only_fields = fields


class RoleCreateUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for Role model."""

    class Meta:
        model = Role
        fields = ['name', 'label']

    def validate_name(self, value):
        """Ensure name is lowercase and alphanumeric with underscores."""
        if not value:
            raise serializers.ValidationError('name is required.')
        if not value.replace('_', '').isalnum():
            raise serializers.ValidationError('name must be alphanumeric with underscores only.')
        return value.lower()


# -----------------------------------------------------------------------------
# User Serializers
# -----------------------------------------------------------------------------


class UserSerializer(serializers.ModelSerializer):
    """Read-only serializer for User model with nested role."""

    role = RoleSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'calendar_color',
            'role',
            'date_joined',
            'last_login',
        ]
        read_only_fields = fields


class UserListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for User lists (no nested objects)."""

    role_name = serializers.CharField(source='role.name', read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'role_name']
        read_only_fields = fields


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users."""

    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.using('default').all(),
        required=False,
        allow_null=True,
    )
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'password',
            'calendar_color',
            'role',
        ]

    def validate_email(self, value):
        """Ensure email is unique."""
        if User.objects.using('default').filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def create(self, validated_data):
        """Create user with hashed password."""
        password = validated_data.pop('password')
        user = User.objects.db_manager('default').create_user(
            password=password,
            **validated_data,
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating existing users."""

    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.using('default').all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = [
            'email',
            'first_name',
            'last_name',
            'is_active',
            'calendar_color',
            'role',
        ]

    def validate_email(self, value):
        """Ensure email is unique (excluding current user)."""
        instance = self.instance
        qs = User.objects.using('default').filter(email=value)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value


class UserPasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change."""

    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)

    def validate_old_password(self, value):
        """Verify old password is correct."""
        user = self.context.get('user')
        if user is None or not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value


# -----------------------------------------------------------------------------
# AuditLog Serializers
# -----------------------------------------------------------------------------


class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for AuditLog model."""

    user_display = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'user_display',
            'role_name',
            'action',
            'patient_id',
            'timestamp',
            'meta',
        ]
        read_only_fields = fields

    def get_user_display(self, obj):
        """Return username or 'System' if no user."""
        user = getattr(obj, 'user', None)
        if user is None:
            return 'System'
        return getattr(user, 'username', 'Unknown')


class AuditLogListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for AuditLog lists."""

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'patient_id', 'timestamp', 'role_name']
        read_only_fields = fields


# -----------------------------------------------------------------------------
# Authentication Serializers
# -----------------------------------------------------------------------------


class LoginSerializer(serializers.Serializer):
    """Serializer for user login.

    Validates credentials and returns user with role info.
    """

    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        from django.contrib.auth import authenticate

        username = attrs.get('username')
        password = attrs.get('password')

        if not username or not password:
            raise serializers.ValidationError('Username and password are required.')

        # Authenticate against default database
        user = authenticate(username=username, password=password)

        if user is None:
            raise serializers.ValidationError('Invalid credentials.')

        if not user.is_active:
            raise serializers.ValidationError('User account is disabled.')

        attrs['user'] = user
        return attrs


class RefreshSerializer(serializers.Serializer):
    """Serializer for token refresh.

    Validates refresh token and returns new access token.
    """

    refresh = serializers.CharField(required=True)

    def validate_refresh(self, value):
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        try:
            token = RefreshToken(value)
            # Token is valid, return it
            return value
        except TokenError as e:
            raise serializers.ValidationError(f'Invalid or expired refresh token: {str(e)}')


class UserMeSerializer(serializers.ModelSerializer):
    """Serializer for the /auth/me/ endpoint.

    Returns current user info with role details.
    """

    role = RoleSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'calendar_color',
            'role',
        ]
        read_only_fields = fields
