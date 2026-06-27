from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class Produk(models.Model):
    KATEGORI_CHOICES = [
        ('Tepung Terigu', 'Tepung Terigu'),
        ('Tepung Beras', 'Tepung Beras'),
        ('Tepung Tapioka', 'Tepung Tapioka'),
        ('Tepung Spesial', 'Tepung Spesial'),
    ]
    nama      = models.CharField(max_length=200)
    kategori  = models.CharField(max_length=50, choices=KATEGORI_CHOICES)
    deskripsi = models.TextField()
    harga     = models.IntegerField()
    berat     = models.CharField(max_length=50)
    stok      = models.IntegerField(default=0)
    emoji     = models.CharField(max_length=10, default='🌾')
    gambar    = models.ImageField(upload_to='produk/', blank=True, null=True)
    tersedia  = models.BooleanField(default=True)
    dibuat    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nama

    class Meta:
        verbose_name = 'Produk'
        verbose_name_plural = 'Daftar Produk'


class Pesanan(models.Model):
    STATUS_CHOICES = [
        ('menunggu',    'Menunggu Pembayaran'),
        ('dibayar',     'Sudah Dibayar'),
        ('diproses',    'Sedang Diproses'),
        ('dikirim',     'Sedang Dikirim'),
        ('selesai',     'Selesai'),
        ('dibatalkan',  'Dibatalkan'),
    ]
    user               = models.ForeignKey(User, on_delete=models.CASCADE)
    nomor_pesanan      = models.CharField(max_length=20, unique=True)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default='menunggu')
    nama_penerima      = models.CharField(max_length=200)
    telepon            = models.CharField(max_length=20)
    alamat             = models.TextField()
    metode_pengiriman  = models.CharField(max_length=100)
    metode_pembayaran  = models.CharField(max_length=100)
    ongkir             = models.IntegerField(default=0)
    total              = models.IntegerField(default=0)
    bukti_bayar        = models.ImageField(upload_to='bukti_bayar/', null=True, blank=True)
    alasan_batal       = models.TextField(blank=True, null=True)
    dibuat             = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nomor_pesanan

    class Meta:
        verbose_name = 'Pesanan'
        verbose_name_plural = 'Daftar Pesanan'


class ItemPesanan(models.Model):
    pesanan      = models.ForeignKey(Pesanan, on_delete=models.CASCADE, related_name='items')
    produk_nama  = models.CharField(max_length=200)
    produk_emoji = models.CharField(max_length=10)
    produk_gambar = models.CharField(max_length=500, blank=True, default='')
    harga        = models.IntegerField()
    jumlah       = models.IntegerField()

    def subtotal(self):
        return self.harga * self.jumlah

    def gambar_url(self):
        if not self.produk_gambar:
            return ''
        path = str(self.produk_gambar).replace('\\', '/')
        if path.startswith(('http://', 'https://')):
            return path
        if path.startswith('/'):
            return path
        media_url = str(getattr(settings, 'MEDIA_URL', '/media/'))
        return f"{media_url.rstrip('/')}/{path.lstrip('/')}"


class DompetAdmin(models.Model):
    saldo      = models.BigIntegerField(default=0)
    diperbarui = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Saldo: Rp{self.saldo:,}'

    class Meta:
        verbose_name = 'Dompet Admin'
        verbose_name_plural = 'Dompet Admin'


class RiwayatDompet(models.Model):
    pesanan    = models.ForeignKey(Pesanan, on_delete=models.SET_NULL, null=True)
    jumlah     = models.IntegerField()
    keterangan = models.CharField(max_length=200)
    dibuat     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'+Rp{self.jumlah:,} - {self.keterangan}'

    class Meta:
        verbose_name = 'Riwayat Dompet'
        verbose_name_plural = 'Riwayat Dompet'


class RekeningAdmin(models.Model):
    METODE_CHOICES = [
        ('transfer', 'Transfer Bank'),
        ('qris',     'QRIS'),
    ]
    metode    = models.CharField(max_length=20, choices=METODE_CHOICES)
    nama_bank = models.CharField(max_length=100, help_text="Contoh: Bank BCA")
    nomor     = models.CharField(max_length=100, help_text="Nomor rekening atau nomor QRIS")
    atas_nama = models.CharField(max_length=100, help_text="Nama pemilik rekening")
    aktif     = models.BooleanField(default=True)
    qr_code   = models.ImageField(upload_to='qris/', blank=True, null=True, help_text="Upload foto/gambar QR Code QRIS")

    def __str__(self):
        return f"{self.nama_bank} - {self.nomor}"

    class Meta:
        verbose_name = 'Rekening Admin'
        verbose_name_plural = 'Rekening Admin'


class Ulasan(models.Model):
    pesanan     = models.ForeignKey(Pesanan, on_delete=models.CASCADE, related_name='ulasan')
    produk_nama = models.CharField(max_length=200)
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    rating      = models.IntegerField(default=5)
    komentar    = models.TextField()
    dibuat      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} - {self.produk_nama} ({self.rating}★)'

    class Meta:
        verbose_name = 'Ulasan'
        verbose_name_plural = 'Daftar Ulasan'

class PoinPelanggan(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='poin')
    total_poin = models.IntegerField(default=0)
    diperbarui = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} — {self.total_poin} poin'

    class Meta:
        verbose_name = 'Poin Pelanggan'
        verbose_name_plural = 'Daftar Poin Pelanggan'


class RiwayatPoin(models.Model):
    TIPE_CHOICES = [
        ('tambah', 'Poin Ditambah'),
        ('tukar',  'Poin Ditukarkan'),
    ]
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    tipe       = models.CharField(max_length=10, choices=TIPE_CHOICES)
    jumlah     = models.IntegerField()
    keterangan = models.CharField(max_length=200)
    dibuat     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} {self.tipe} {self.jumlah} poin'

    class Meta:
        verbose_name = 'Riwayat Poin'
        verbose_name_plural = 'Riwayat Poin'


class KonfigurasiPoin(models.Model):
    poin_per_pesanan    = models.IntegerField(default=1, help_text='Poin yang didapat per pesanan selesai')
    target_tukar        = models.IntegerField(default=10, help_text='Jumlah poin yang dibutuhkan untuk ditukar')
    nilai_diskon        = models.IntegerField(default=10000, help_text='Nilai diskon (Rp) per penukaran')
    aktif               = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.poin_per_pesanan} poin/pesanan → {self.target_tukar} poin = Rp{self.nilai_diskon:,}'

    class Meta:
        verbose_name = 'Konfigurasi Poin'
        verbose_name_plural = 'Konfigurasi Poin'
