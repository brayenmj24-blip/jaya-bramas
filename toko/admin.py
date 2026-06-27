from django.contrib import admin
from django.contrib.admin import AdminSite
from django.db.models import Sum
from django.utils import timezone
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe
from django.http import JsonResponse
from .models import (
    Pesanan, Produk, ItemPesanan, DompetAdmin,
    RiwayatDompet, RekeningAdmin, Ulasan
)
import calendar


class ItemPesananInline(admin.TabularInline):
    model = ItemPesanan
    extra = 0
    readonly_fields = ('produk_nama', 'produk_emoji', 'harga', 'jumlah')
    can_delete = False

def get_admin_index_context(request):
    from .models import Pesanan, DompetAdmin, ItemPesanan
    from django.db.models import Sum, Count
    from django.utils import timezone
    import calendar

    now = timezone.now()

    stat_menunggu = Pesanan.objects.filter(status='menunggu').count()
    stat_dibayar  = Pesanan.objects.filter(status='dibayar').count()
    stat_selesai  = Pesanan.objects.filter(
        status='selesai',
        dibuat__year=now.year,
        dibuat__month=now.month
    ).count()

    try:
        dompet = DompetAdmin.objects.get(pk=1)
        saldo  = f"Rp{dompet.saldo:,.0f}".replace(',', '.')
    except DompetAdmin.DoesNotExist:
        saldo = "Rp0"

    laporan = []
    for i in range(5, -1, -1):
        bulan_dt = now.replace(day=1) - timezone.timedelta(days=i*28)
        total = Pesanan.objects.filter(
            status__in=['diproses','dikirim','selesai'],
            dibuat__year=bulan_dt.year,
            dibuat__month=bulan_dt.month
        ).aggregate(t=Sum('total'))['t'] or 0
        laporan.append({
            'bulan': bulan_dt.strftime('%b %y'),
            'total': total,
            'total_fmt': f"Rp{total:,.0f}".replace(',', '.'),
        })
    max_total = max((b['total'] for b in laporan), default=1) or 1
    for b in laporan:
        b['persen'] = int(b['total'] / max_total * 100)

    from django.db.models import Sum as DSum
    terlaris_raw = ItemPesanan.objects.values('produk_nama', 'produk_emoji').annotate(
        total_terjual=DSum('jumlah'),
        pendapatan=DSum('harga')
    ).order_by('-total_terjual')[:5]
    produk_terlaris = []
    for p in terlaris_raw:
        produk_terlaris.append({
            'nama': p['produk_nama'],
            'emoji': p['produk_emoji'] or '🌾',
            'total_terjual': p['total_terjual'],
            'pendapatan_fmt': f"Rp{p['pendapatan']:,.0f}".replace(',', '.'),
        })

    ringkasan_status = [
        {'label':'Menunggu','icon':'⏳','color':'#F59E0B','jumlah': Pesanan.objects.filter(status='menunggu').count()},
        {'label':'Dibayar','icon':'💳','color':'#3B82F6','jumlah': Pesanan.objects.filter(status='dibayar').count()},
        {'label':'Diproses','icon':'⚙️','color':'#8B5CF6','jumlah': Pesanan.objects.filter(status='diproses').count()},
        {'label':'Dikirim','icon':'🚚','color':'#06B6D4','jumlah': Pesanan.objects.filter(status='dikirim').count()},
        {'label':'Selesai','icon':'✅','color':'#10B981','jumlah': Pesanan.objects.filter(status='selesai').count()},
        {'label':'Dibatalkan','icon':'❌','color':'#EF4444','jumlah': Pesanan.objects.filter(status='dibatalkan').count()},
    ]

    return {
        'stat_menunggu': stat_menunggu,
        'stat_dibayar':  stat_dibayar,
        'stat_selesai':  stat_selesai,
        'saldo_admin':   saldo,
        'laporan_bulanan': laporan,
        'produk_terlaris': produk_terlaris,
        'ringkasan_status': ringkasan_status,
    }

original_index = admin.site.__class__.index
def custom_index(self, request, extra_context=None):
    extra_context = extra_context or {}
    extra_context.update(get_admin_index_context(request))
    return original_index(self, request, extra_context)
admin.site.__class__.index = custom_index


@admin.register(Pesanan)
class PesananAdmin(admin.ModelAdmin):
    list_display = ('nomor_pesanan', 'user', 'nama_penerima', 'total_rupiah',
                    'status_badge', 'bukti_bayar_link', 'aksi_konfirmasi', 'dibuat')
    list_filter = ('status', 'dibuat')
    search_fields = ('nomor_pesanan', 'nama_penerima', 'user__username')
    readonly_fields = ('nomor_pesanan', 'dibuat', 'bukti_bayar_preview')
    inlines = [ItemPesananInline]
    ordering = ('-dibuat',)
    change_list_template = 'admin/pesanan_change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:pesanan_id>/konfirmasi/',
                 self.admin_site.admin_view(self.konfirmasi_view),
                 name='konfirmasi_pembayaran'),
            path('<int:pesanan_id>/kirim/',
                 self.admin_site.admin_view(self.kirim_view),
                 name='kirim_pesanan'),
            path('<int:pesanan_id>/selesai/',
                 self.admin_site.admin_view(self.selesai_view),
                 name='selesai_pesanan'),
        ]
        return custom + urls

    def konfirmasi_view(self, request, pesanan_id):
        if request.method == 'POST':
            try:
                pesanan = Pesanan.objects.get(pk=pesanan_id)
                if pesanan.status == 'dibayar':
                    pesanan.status = 'diproses'
                    pesanan.save()
                    dompet, _ = DompetAdmin.objects.get_or_create(pk=1)
                    dompet.saldo += pesanan.total
                    dompet.save()
                    RiwayatDompet.objects.create(
                        pesanan=pesanan,
                        jumlah=pesanan.total,
                        keterangan=f'Konfirmasi pembayaran #{pesanan.nomor_pesanan}'
                    )
                    return JsonResponse({'success': True, 'nomor': pesanan.nomor_pesanan})
                return JsonResponse({'success': False, 'error': 'Status pesanan tidak valid'})
            except Pesanan.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Pesanan tidak ditemukan'})
        return JsonResponse({'success': False, 'error': 'Method tidak diizinkan'})

    def kirim_view(self, request, pesanan_id):
        from django.shortcuts import redirect
        try:
            pesanan = Pesanan.objects.get(pk=pesanan_id)
            if pesanan.status == 'diproses':
                pesanan.status = 'dikirim'
                pesanan.save()
                self.message_user(request, f'🚚 Pesanan {pesanan.nomor_pesanan} ditandai sudah dikirim!')
        except Pesanan.DoesNotExist:
            self.message_user(request, 'Pesanan tidak ditemukan.', level='error')
        return redirect('../../')

    def selesai_view(self, request, pesanan_id):
        from django.shortcuts import redirect
        from toko.views import _tambah_poin
        try:
            pesanan = Pesanan.objects.get(pk=pesanan_id)
            if pesanan.status == 'dikirim':
                pesanan.status = 'selesai'
                pesanan.save()
                _tambah_poin(pesanan.user, f'Pesanan #{pesanan.nomor_pesanan} selesai')
                self.message_user(request, f'✅ Pesanan {pesanan.nomor_pesanan} selesai! Poin ditambahkan ke {pesanan.user.username}.')
        except Pesanan.DoesNotExist:
            self.message_user(request, 'Pesanan tidak ditemukan.', level='error')
        return redirect('../../')

    def total_rupiah(self, obj):
        return f'Rp{obj.total:,.0f}'.replace(',', '.')
    total_rupiah.short_description = 'Total'

    def status_badge(self, obj):
        warna = {
            'menunggu':   ('#F59E0B', '#FEF9EC', 'Menunggu Pembayaran'),
            'dibayar':    ('#3B82F6', '#EFF6FF', 'Sudah Dibayar'),
            'diproses':   ('#8B5CF6', '#EDE9FE', 'Sedang Diproses'),
            'dikirim':    ('#06B6D4', '#ECFEFF', 'Sedang Dikirim'),
            'selesai':    ('#10B981', '#ECFDF5', 'Selesai'),
            'dibatalkan': ('#EF4444', '#FEF2F2', 'Dibatalkan'),
        }
        color, bg, label = warna.get(obj.status, ('#888', '#f5f5f5', obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:4px 12px;border-radius:100px;'
            'font-size:11px;font-weight:600">{}</span>',
            bg, color, label
        )
    status_badge.short_description = 'Status'

    def bukti_bayar_link(self, obj):
        if obj.bukti_bayar:
            return format_html(
                '<button type="button" onclick="lihatBukti(\'{}\', \'{}\')" '
                'style="background:#3B82F6;color:white;border:none;border-radius:6px;'
                'padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer">'
                '📎 Lihat</button>',
                obj.bukti_bayar.url, obj.nomor_pesanan
            )
        return mark_safe('<span style="color:#9CA3AF;font-size:12px">Belum ada</span>')
    bukti_bayar_link.short_description = 'Bukti Bayar'

    def bukti_bayar_preview(self, obj):
        if obj.bukti_bayar:
            return format_html(
                '<img src="{}" style="max-width:300px;border-radius:8px">',
                obj.bukti_bayar.url
            )
        return mark_safe('<span style="color:#9CA3AF">Belum ada bukti bayar</span>')
    bukti_bayar_preview.short_description = 'Preview Bukti'

    def aksi_konfirmasi(self, obj):
        if obj.status == 'dibayar':
            url     = reverse('admin:konfirmasi_pembayaran', args=[obj.pk])
            nominal = f'Rp{obj.total:,.0f}'.replace(',', '.')
            nama    = obj.nama_penerima
            return format_html(
                '<button type="button" onclick="bukaModalKonfirmasi(\'{}\', \'{}\', \'{}\', \'{}\')" '
                'style="background:#10B981;color:white;border:none;border-radius:6px;'
                'padding:6px 12px;font-size:12px;font-weight:600;cursor:pointer">'
                '✓ Konfirmasi</button>',
                url, obj.nomor_pesanan, nominal, nama
            )
        elif obj.status == 'diproses':
            url = reverse('admin:kirim_pesanan', args=[obj.pk])
            return format_html(
                '<button type="button" onclick="bukaModalKirim(\'{}\', \'{}\')" '
                'style="background:#3B82F6;color:white;border:none;border-radius:6px;'
                'padding:6px 12px;font-size:12px;font-weight:600;cursor:pointer">'
                '🚚 Kirim</button>',
                url, obj.nomor_pesanan
            )
        elif obj.status == 'dikirim':
            url = reverse('admin:selesai_pesanan', args=[obj.pk])
            return format_html(
                '<button type="button" onclick="bukaModalSelesai(\'{}\', \'{}\')" '
                'style="background:#8B5CF6;color:white;border:none;border-radius:6px;'
                'padding:6px 12px;font-size:12px;font-weight:600;cursor:pointer">'
                '✅ Selesai</button>',
                url, obj.nomor_pesanan
            )
        elif obj.status == 'menunggu':
            return mark_safe('<span style="color:#F59E0B;font-size:12px">⏳ Menunggu Bayar</span>')
        elif obj.status == 'selesai':
            return mark_safe('<span style="color:#10B981;font-size:12px">✅ Selesai</span>')
        return mark_safe('<span style="color:#9CA3AF;font-size:12px">—</span>')
    aksi_konfirmasi.short_description = 'Aksi'


@admin.register(Produk)
class ProdukAdmin(admin.ModelAdmin):
    list_display = ('nama', 'kategori', 'harga_rupiah', 'stok', 'tersedia')
    list_filter = ('kategori', 'tersedia')
    search_fields = ('nama',)
    list_editable = ('tersedia', 'stok')
    ordering = ('kategori', 'nama')

    def harga_rupiah(self, obj):
        return f'Rp{obj.harga:,.0f}'.replace(',', '.')
    harga_rupiah.short_description = 'Harga'


@admin.register(DompetAdmin)
class DompetAdminAdmin(admin.ModelAdmin):
    list_display = ('saldo_rupiah', 'diperbarui')
    readonly_fields = ('diperbarui',)

    def saldo_rupiah(self, obj):
        return f'Rp{obj.saldo:,.0f}'.replace(',', '.')
    saldo_rupiah.short_description = 'Saldo'

    def has_add_permission(self, request):
        return not DompetAdmin.objects.exists()


@admin.register(RiwayatDompet)
class RiwayatDompetAdmin(admin.ModelAdmin):
    list_display = ('keterangan', 'jumlah_rupiah', 'dibuat')
    readonly_fields = ('pesanan', 'jumlah', 'keterangan', 'dibuat')
    ordering = ('-dibuat',)

    def jumlah_rupiah(self, obj):
        return f'Rp{obj.jumlah:,.0f}'.replace(',', '.')
    jumlah_rupiah.short_description = 'Jumlah'


@admin.register(RekeningAdmin)
class RekeningAdminAdmin(admin.ModelAdmin):
    list_display = ('nama_bank', 'metode', 'nomor', 'atas_nama', 'aktif')
    list_editable = ('aktif',)
    list_filter = ('metode', 'aktif')


@admin.register(Ulasan)
class UlasanAdmin(admin.ModelAdmin):
    list_display = ('user', 'produk_nama', 'rating_bintang', 'komentar_pendek', 'dibuat')
    list_filter  = ('rating', 'dibuat')
    search_fields = ('user__username', 'produk_nama', 'komentar')
    readonly_fields = ('pesanan', 'user', 'produk_nama', 'rating', 'komentar', 'dibuat')
    ordering = ('-dibuat',)

    def rating_bintang(self, obj):
        return '★' * obj.rating + '☆' * (5 - obj.rating)
    rating_bintang.short_description = 'Rating'

    def komentar_pendek(self, obj):
        return obj.komentar[:60] + '...' if len(obj.komentar) > 60 else obj.komentar
    komentar_pendek.short_description = 'Komentar'



from .models import PoinPelanggan, RiwayatPoin, KonfigurasiPoin

@admin.register(KonfigurasiPoin)
class KonfigurasiPoinAdmin(admin.ModelAdmin):
    list_display = ('poin_per_pesanan', 'target_tukar', 'nilai_diskon_rupiah', 'aktif')

    def nilai_diskon_rupiah(self, obj):
        return f'Rp{obj.nilai_diskon:,.0f}'.replace(',', '.')
    nilai_diskon_rupiah.short_description = 'Nilai Diskon'

    def has_add_permission(self, request):
        return not KonfigurasiPoin.objects.exists()


@admin.register(PoinPelanggan)
class PoinPelangganAdmin(admin.ModelAdmin):
    list_display  = ('user', 'total_poin', 'status_poin', 'diperbarui')
    search_fields = ('user__username', 'user__first_name')
    ordering      = ('-total_poin',)
    readonly_fields = ('user', 'total_poin', 'diperbarui')

    def status_poin(self, obj):
        try:
            cfg = KonfigurasiPoin.objects.get(pk=1)
            sisa = cfg.target_tukar - obj.total_poin
            if sisa <= 0:
                return format_html('<span style="color:#10B981;font-weight:600">✅ Bisa ditukar!</span>')
            return format_html('<span style="color:#F59E0B">⬜ Butuh {} poin lagi</span>', sisa)
        except:
            return '—'
    status_poin.short_description = 'Status'


@admin.register(RiwayatPoin)
class RiwayatPoinAdmin(admin.ModelAdmin):
    list_display  = ('user', 'tipe', 'jumlah', 'keterangan', 'dibuat')
    list_filter   = ('tipe', 'dibuat')
    search_fields = ('user__username',)
    ordering      = ('-dibuat',)
    readonly_fields = ('user', 'tipe', 'jumlah', 'keterangan', 'dibuat')