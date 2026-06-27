from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_default_users(sender, **kwargs):
    from django.contrib.auth import get_user_model

    User = get_user_model()

    if not User.objects.filter(username='bramasadmin').exists():
        admin = User.objects.create_user(
            username='bramasadmin',
            email='admin@gmail.com',
            password='Admin@1234',
            first_name='Admin',
        )
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

    if not User.objects.filter(username='brayenmj24@gmail.com').exists():
        customer = User.objects.create_user(
            username='brayenmj24@gmail.com',
            email='brayenmj24@gmail.com',
            password='Customer@1234',
            first_name='Customer',
        )
        customer.is_staff = False
        customer.is_superuser = False
        customer.save()


class TokoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'toko'

    def ready(self):
        post_migrate.connect(create_default_users, sender=self)
