from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db import transaction
from .models import Produk, Pesanan, ItemPesanan, DompetAdmin, RiwayatDompet, RekeningAdmin, Ulasan
import json, random


@ensure_csrf_cookie
def login_page(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('/admin/')
        return redirect('home')
    ajax_request = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')
    if request.method == 'POST' and ajax_request:
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_staff:
                return JsonResponse({'success': True, 'redirect': '/admin/'})
            return JsonResponse({'success': True, 'redirect': '/home/'})
        return JsonResponse({'success': False, 'error': 'Username atau password salah!'})
    error = ''
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_staff:
                return redirect('/admin/')
            return redirect('home')
        else:
            error = 'Username atau password salah!'
    return render(request, 'login.html', {'error': error})


@ensure_csrf_cookie
def register_user(request):
    if request.user.is_authenticated:
        return redirect('home')
    ajax_request = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')
    if request.method == 'POST' and ajax_request:
        nama     = request.POST.get('nama', '').strip()
        email    = request.POST.get('email', '').strip()
        telepon  = request.POST.get('telepon', '').strip()
        password = request.POST.get('password', '')
        if not nama or not email or not telepon or not password:
            return JsonResponse({'success': False, 'error': 'Semua kolom wajib diisi'})
        if len(password) < 8:
            return JsonResponse({'success': False, 'error': 'Kata sandi minimal 8 karakter'})
        if User.objects.filter(username=email).exists():
            return JsonResponse({'success': False, 'error': 'Email sudah terdaftar'})
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=nama,
        )
        user.last_name = telepon
        user.save()
        login(request, user)
        return JsonResponse({'success': True, 'redirect': '/home/'})
    return JsonResponse({'success': False, 'error': 'Metode tidak diizinkan'})


@ensure_csrf_cookie
def home(request):
    from django.db.models import Avg, Count
    produk = Produk.objects.filter(tersedia=True)
    rating_toko = Ulasan.objects.aggregate(
        rata=Avg('rating'),
        total=Count('id')
    )
    rata_toko = round(rating_toko['rata'] or 4.9, 1)
    total_ulasan = rating_toko['total'] or 0
    return render(request, 'index.html', {
        'produk_db': produk,
        'user': request.user,
        'rata_toko': rata_toko,
        'total_ulasan': total_ulasan,
    })

@login_required(login_url='/login/')
def buat_pesanan(request):
    if request.method == 'POST':
        data  = json.loads(request.body)
        items = data.get('items', [])

        with transaction.atomic():
            stok_errors = []
            produk_map  = {}

            for item in items:
                produk_id = item.get('id')
                qty       = item.get('qty', 0)
                try:
                    produk = Produk.objects.select_for_update().get(id=produk_id, tersedia=True)
                    if produk.stok < qty:
                        stok_errors.append(
                            f"Stok '{produk.nama}' tidak cukup (tersisa {produk.stok}, diminta {qty})"
                        )
                    else:
                        produk_map[produk_id] = produk
                except Produk.DoesNotExist:
                    stok_errors.append(f"Produk ID {produk_id} tidak tersedia")

            if stok_errors:
                return JsonResponse({'success': False, 'errors': stok_errors})

            while True:
                nomor = 'BJ-' + str(random.randint(100000, 999999))
                if not Pesanan.objects.filter(nomor_pesanan=nomor).exists():
                    break

            metode_pengiriman = data.get('pengiriman', 'Pengiriman')
            ongkir = _hitung_ongkir(data.get('provinsi', ''), metode_pengiriman)
            # Harga diambil dari DB (produk_map), bukan dari request client
            subtotal = sum(produk_map[item['id']].harga * item['qty'] for item in items)

            pesanan = Pesanan.objects.create(
                user=request.user,
                nomor_pesanan=nomor,
                nama_penerima=data.get('nama'),
                telepon=data.get('telepon'),
                alamat=data.get('alamat'),
                metode_pengiriman=metode_pengiriman,
                metode_pembayaran=data.get('pembayaran'),
                ongkir=ongkir,
                total=subtotal + ongkir,
                status='menunggu'
            )

            for item in items:
                produk = produk_map[item['id']]
                ItemPesanan.objects.create(
                    pesanan=pesanan,
                    produk_nama=item['name'],
                    produk_emoji=item['emoji'],
                    produk_gambar=produk.gambar.name.replace('\\', '/') if produk.gambar else '',
                    harga=produk.harga,   # dari DB, bukan dari client
                    jumlah=item['qty']
                )
                produk.stok -= item['qty']
                if produk.stok <= 0:
                    produk.stok     = 0
                    produk.tersedia = False
                produk.save()

        return JsonResponse({'success': True, 'nomor': nomor, 'id': pesanan.id})
    return JsonResponse({'success': False})


@login_required(login_url='/login/')
def pembayaran(request, pesanan_id):
    pesanan           = get_object_or_404(Pesanan, id=pesanan_id, user=request.user)
    rekening_transfer = RekeningAdmin.objects.filter(aktif=True, metode='transfer').first()
    rekening_qris     = RekeningAdmin.objects.filter(aktif=True, metode='qris').first()

    if request.method == 'POST':
        # COD — langsung konfirmasi tanpa upload
        if request.POST.get('cod_confirm'):
            pesanan.status = 'dibayar'
            pesanan.save()
            return redirect('sukses', pesanan_id=pesanan.id)

        # Transfer / QRIS — upload bukti, saldo belum bertambah
        if request.FILES.get('bukti'):
            pesanan.bukti_bayar = request.FILES['bukti']
            pesanan.status = 'dibayar'
            pesanan.save()
            return redirect('sukses', pesanan_id=pesanan.id)

    return render(request, 'pembayaran.html', {
        'pesanan': pesanan,
        'rekening_transfer': rekening_transfer,
        'rekening_qris': rekening_qris,
        'metode': pesanan.metode_pembayaran,
    })


@login_required(login_url='/login/')
def sukses(request, pesanan_id):
    pesanan = get_object_or_404(Pesanan, id=pesanan_id, user=request.user)
    return render(request, 'sukses.html', {'pesanan': pesanan})


@login_required(login_url='/login/')
def ganti_sandi(request):
    pesan = ''
    error = ''
    if request.method == 'POST':
        sandi_lama = request.POST.get('sandi_lama')
        sandi_baru = request.POST.get('sandi_baru')
        konfirmasi = request.POST.get('konfirmasi')
        if not request.user.check_password(sandi_lama):
            error = 'Kata sandi lama salah!'
        elif sandi_baru != konfirmasi:
            error = 'Konfirmasi kata sandi tidak cocok!'
        elif len(sandi_baru) < 8:
            error = 'Kata sandi baru minimal 8 karakter!'
        else:
            request.user.set_password(sandi_baru)
            request.user.save()
            update_session_auth_hash(request, request.user)
            pesan = 'Kata sandi berhasil diubah!'
    return render(request, 'ganti_sandi.html', {'pesan': pesan, 'error': error})


@login_required(login_url='/login/')
def profil(request):
    pesan = ''
    error = ''
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        email      = request.POST.get('email', '').strip()
        telepon    = request.POST.get('telepon', '').strip()
        if not first_name or not email:
            error = 'Nama dan email wajib diisi!'
        else:
            request.user.first_name = first_name
            request.user.email      = email
            if telepon:
                request.user.last_name = telepon
            request.user.save()
            pesan = 'Profil berhasil diperbarui!'
    pesanan = Pesanan.objects.filter(user=request.user).order_by('-dibuat')

    # Mapping nama produk → URL gambar
    gambar_map = {}
    for p in Produk.objects.exclude(gambar='').exclude(gambar=None):
        gambar_map[p.nama] = p.gambar.url

    return render(request, 'profil.html', {
        'user': request.user,
        'pesanan': pesanan,
        'pesan': pesan,
        'error': error,
        'gambar_map': gambar_map,
    })



def logout_page(request):
    if request.method == 'POST':
        logout(request)
    elif request.user.is_authenticated:
        logout(request)
    return redirect('/')

@login_required(login_url='/login/')
def batalkan_pesanan(request, pesanan_id):
    if request.method == 'POST':
        try:
            pesanan = Pesanan.objects.get(pk=pesanan_id, user=request.user)
            if pesanan.status in ['menunggu', 'dibayar']:
                alasan = request.POST.get('alasan', '').strip()
                if not alasan:
                    return JsonResponse({'success': False, 'error': 'Alasan pembatalan wajib diisi'})
                with transaction.atomic():
                    pesanan.status = 'dibatalkan'
                    pesanan.alasan_batal = alasan
                    pesanan.save()
                    # Kembalikan stok produk
                    for item in pesanan.items.all():
                        try:
                            produk = Produk.objects.select_for_update().get(nama=item.produk_nama)
                            produk.stok += item.jumlah
                            produk.tersedia = True
                            produk.save()
                        except Produk.DoesNotExist:
                            pass
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Pesanan tidak bisa dibatalkan pada status ini'})
        except Pesanan.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Pesanan tidak ditemukan'})
    return JsonResponse({'success': False, 'error': 'Metode tidak diizinkan'})

@login_required(login_url='/login/')
def beri_ulasan(request, pesanan_id):
    if request.method == 'POST':
        pesanan = get_object_or_404(Pesanan, id=pesanan_id, user=request.user)
        if pesanan.status != 'selesai':
            return JsonResponse({'success': False, 'error': 'Hanya pesanan selesai yang bisa diulas'})
        produk_nama = request.POST.get('produk_nama', '').strip()
        rating      = max(1, min(5, int(request.POST.get('rating', 5))))
        komentar    = request.POST.get('komentar', '').strip()
        if not komentar:
            return JsonResponse({'success': False, 'error': 'Komentar tidak boleh kosong'})
        ulasan, created = Ulasan.objects.get_or_create(
            pesanan=pesanan,
            produk_nama=produk_nama,
            user=request.user,
            defaults={'rating': rating, 'komentar': komentar}
        )
        if not created:
            ulasan.rating   = rating
            ulasan.komentar = komentar
            ulasan.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

import openpyxl
from django.http import HttpResponse

@login_required(login_url='/login/')
def export_pesanan_excel(request):
    if not request.user.is_staff:
        return redirect('home')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pesanan"

    # Header
    headers = ['No', 'Nomor Pesanan', 'Nama Penerima', 'Telepon', 
               'Metode Pembayaran', 'Metode Pengiriman', 'Total', 'Status', 'Tanggal']
    ws.append(headers)

    # Data
    pesanan_list = Pesanan.objects.all().order_by('-dibuat')
    for i, p in enumerate(pesanan_list, 1):
        ws.append([
            i,
            p.nomor_pesanan,
            p.nama_penerima,
            p.telepon,
            p.metode_pembayaran,
            p.metode_pengiriman,
            float(p.total),
            p.status,
            p.dibuat.strftime('%d/%m/%Y %H:%M'),
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="pesanan-bramas-jaya.xlsx"'
    wb.save(response)
    return response

def ulasan_produk(request):
    produk_nama = request.GET.get('produk', '')
    if not produk_nama:
        return JsonResponse({'ulasan': [], 'rata_rata': 0, 'total': 0})
    ulasan = Ulasan.objects.filter(produk_nama=produk_nama).order_by('-dibuat')
    data = []
    for u in ulasan:
        data.append({
            'user': u.user.first_name or u.user.username,
            'rating': u.rating,
            'komentar': u.komentar,
            'tanggal': u.dibuat.strftime('%d %b %Y'),
        })
    total = ulasan.count()
    rata = round(sum(u['rating'] for u in data) / total, 1) if total > 0 else 0
    return JsonResponse({'ulasan': data, 'rata_rata': rata, 'total': total})

def _tambah_poin(user, keterangan):
    """Tambah poin ke user setelah pesanan selesai"""
    from .models import PoinPelanggan, RiwayatPoin, KonfigurasiPoin
    try:
        cfg = KonfigurasiPoin.objects.get(pk=1, aktif=True)
    except KonfigurasiPoin.DoesNotExist:
        return
    poin, _ = PoinPelanggan.objects.get_or_create(user=user)
    poin.total_poin += cfg.poin_per_pesanan
    poin.save()
    RiwayatPoin.objects.create(
        user=user,
        tipe='tambah',
        jumlah=cfg.poin_per_pesanan,
        keterangan=keterangan
    )

@login_required(login_url='/login/')
def tukar_poin(request):
    if request.method == 'POST':
        from .models import PoinPelanggan, RiwayatPoin, KonfigurasiPoin
        try:
            cfg = KonfigurasiPoin.objects.get(pk=1, aktif=True)
        except KonfigurasiPoin.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Fitur poin belum dikonfigurasi'})

        poin, _ = PoinPelanggan.objects.get_or_create(user=request.user)

        if poin.total_poin < cfg.target_tukar:
            return JsonResponse({
                'success': False,
                'error': f'Poin tidak cukup. Butuh {cfg.target_tukar} poin, kamu punya {poin.total_poin}'
            })

        # Kurangi poin
        poin.total_poin -= cfg.target_tukar
        poin.save()

        RiwayatPoin.objects.create(
            user=request.user,
            tipe='tukar',
            jumlah=cfg.target_tukar,
            keterangan='Tukar poin untuk diskon'
        )

        return JsonResponse({
            'success': True,
            'diskon': cfg.nilai_diskon,
            'keterangan': f'🎉 Berhasil tukar {cfg.target_tukar} poin → Diskon Rp{cfg.nilai_diskon:,}'.replace(',', '.')
        })

    return JsonResponse({'success': False, 'error': 'Metode tidak diizinkan'})


@login_required(login_url='/login/')
def cek_poin(request):
    from .models import PoinPelanggan, RiwayatPoin, KonfigurasiPoin
    try:
        cfg = KonfigurasiPoin.objects.get(pk=1, aktif=True)
        target = cfg.target_tukar
        nilai_diskon = cfg.nilai_diskon
        poin_per_pesanan = cfg.poin_per_pesanan
    except KonfigurasiPoin.DoesNotExist:
        target = 100
        nilai_diskon = 10000
        poin_per_pesanan = 10

    poin, _ = PoinPelanggan.objects.get_or_create(user=request.user)
    riwayat = RiwayatPoin.objects.filter(user=request.user).order_by('-dibuat')

    # Kalau request dari JS (fetch), kembalikan JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({
            'poin': poin.total_poin,
            'target': target,
            'nilai_diskon': nilai_diskon,
            'poin_per_pesanan': poin_per_pesanan,
            'bisa_tukar': poin.total_poin >= target,
        })

    # Kalau buka halaman biasa, render template
    return render(request, 'cek_poin.html', {
        'poin': poin,
        'riwayat': riwayat,
        'target': target,
        'nilai_diskon': nilai_diskon,
    })


# Daftar provinsi di Pulau Jawa (dipakai untuk tentukan tarif ongkir)
PROVINSI_JAWA = {
    'banten', 'dki jakarta', 'di yogyakarta', 'daerah istimewa yogyakarta',
    'jawa barat', 'jawa tengah', 'jawa timur',
}

def _hitung_ongkir(provinsi_nama, metode_pengiriman):
    """Tentukan ongkir flat berdasarkan area & metode pengiriman."""
    from django.conf import settings
    if metode_pengiriman == 'Ambil di Toko':
        return 0
    if (provinsi_nama or '').strip().lower() in PROVINSI_JAWA:
        return settings.ONGKIR_JAWA
    return settings.ONGKIR_LUAR_JAWA

def get_provinsi(request):
    """Daftar provinsi Indonesia (statis) untuk dropdown checkout."""
    daftar = [
        {"nama": "Aceh"}, {"nama": "Bali"}, {"nama": "Bangka Belitung"},
        {"nama": "Banten"}, {"nama": "Bengkulu"}, {"nama": "DI Yogyakarta"},
        {"nama": "DKI Jakarta"}, {"nama": "Gorontalo"}, {"nama": "Jambi"},
        {"nama": "Jawa Barat"}, {"nama": "Jawa Tengah"}, {"nama": "Jawa Timur"},
        {"nama": "Kalimantan Barat"}, {"nama": "Kalimantan Selatan"},
        {"nama": "Kalimantan Tengah"}, {"nama": "Kalimantan Timur"},
        {"nama": "Kalimantan Utara"}, {"nama": "Kepulauan Riau"},
        {"nama": "Lampung"}, {"nama": "Maluku"}, {"nama": "Maluku Utara"},
        {"nama": "Nusa Tenggara Barat"}, {"nama": "Nusa Tenggara Timur"},
        {"nama": "Papua"}, {"nama": "Papua Barat"}, {"nama": "Riau"},
        {"nama": "Sulawesi Barat"}, {"nama": "Sulawesi Selatan"},
        {"nama": "Sulawesi Tengah"}, {"nama": "Sulawesi Tenggara"},
        {"nama": "Sulawesi Utara"}, {"nama": "Sumatera Barat"},
        {"nama": "Sumatera Selatan"}, {"nama": "Sumatera Utara"},
    ]
    for p in daftar:
        p['jawa'] = p['nama'].lower() in PROVINSI_JAWA
    return JsonResponse({'results': daftar})

def cek_ongkir(request):
    """Hitung ongkir flat berdasarkan provinsi tujuan & metode pengiriman."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method tidak diizinkan'}, status=405)
    provinsi  = request.POST.get('provinsi', '')
    metode    = request.POST.get('metode', 'Pengiriman')
    ongkir    = _hitung_ongkir(provinsi, metode)
    return JsonResponse({'ongkir': ongkir, 'jawa': provinsi.strip().lower() in PROVINSI_JAWA})
