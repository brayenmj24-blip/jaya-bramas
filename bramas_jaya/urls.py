from django.contrib import admin
from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from toko import views

admin.site.logout_template = None

urlpatterns = [
    path('admin/logout/', views.logout_page, name='admin-logout'),
    path('admin/', admin.site.urls),
    path('', views.home, name='home-root'),
    path('login/', views.login_page, name='login'),
    path('home/', views.home, name='home'),
    path('buat-pesanan/', views.buat_pesanan, name='buat_pesanan'),
    path('register/', views.register_user, name='register'),
    path('pembayaran/<int:pesanan_id>/', views.pembayaran, name='pembayaran'),
    path('sukses/<int:pesanan_id>/', views.sukses, name='sukses'),
    path('ganti-sandi/', views.ganti_sandi, name='ganti_sandi'),
    path('logout/', views.logout_page, name='logout'),
    path('profil/', views.profil, name='profil'),
    path('profil/batalkan/<int:pesanan_id>/', views.batalkan_pesanan, name='batalkan_pesanan'),
    path('profil/ulasan/<int:pesanan_id>/', views.beri_ulasan, name='beri_ulasan'),
    path('export-pesanan/', views.export_pesanan_excel, name='export_pesanan'),
    path('ulasan-produk/', views.ulasan_produk, name='ulasan_produk'),
    path('cek-poin/', views.cek_poin, name='cek_poin'),
    path('tukar-poin/', views.tukar_poin, name='tukar_poin'),
    path('get-provinsi/', views.get_provinsi, name='get_provinsi'),
    path('cek-ongkir/', views.cek_ongkir, name='cek_ongkir'),
]

# Serve media files (foto produk, bukti bayar, QRIS).
# Django static() hanya aktif saat DEBUG=True, jadi tambahkan fallback
# untuk deployment production jika hosting belum melayani /media/ secara terpisah.
if settings.MEDIA_URL.startswith('/'):
    if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    else:
        urlpatterns += [
            re_path(r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'), serve, {'document_root': settings.MEDIA_ROOT}),
        ]
