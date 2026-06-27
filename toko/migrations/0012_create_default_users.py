from django.db import migrations


def create_default_users(apps, schema_editor):
    User = apps.get_model('auth', 'User')

    admin_email = 'admin@gmail.com'
    admin_username = 'bramasadmin'
    admin_password = 'Admin@1234'
    if not User.objects.filter(username=admin_username).exists():
        user = User.objects.create_user(
            username=admin_username,
            email=admin_email,
            password=admin_password,
            first_name='Admin',
        )
        user.is_staff = True
        user.is_superuser = True
        user.save()

    customer_email = 'brayenmj24@gmail.com'
    customer_username = 'brayenmj24@gmail.com'
    customer_password = 'Customer@1234'
    if not User.objects.filter(username=customer_username).exists():
        user = User.objects.create_user(
            username=customer_username,
            email=customer_email,
            password=customer_password,
            first_name='Customer',
        )
        user.is_staff = False
        user.is_superuser = False
        user.save()


class Migration(migrations.Migration):

    dependencies = [
        ('toko', '0011_delete_kupon_itempesanan_produk_gambar'),
    ]

    operations = [
        migrations.RunPython(create_default_users, reverse_code=migrations.RunPython.noop),
    ]
