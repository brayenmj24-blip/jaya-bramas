from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticate using either username or email (case-insensitive)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        username = username.strip()
        if not username:
            return None

        users = UserModel.objects.filter(username__iexact=username)
        if not users.exists():
            users = UserModel.objects.filter(email__iexact=username)

        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

        return None
