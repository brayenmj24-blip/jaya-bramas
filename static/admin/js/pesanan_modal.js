(function() {
  // Buat overlay sekali
  function buatOverlay() {
    if (document.getElementById('bj-overlay')) return;
    const el = document.createElement('div');
    el.id = 'bj-overlay';
    el.className = 'bj-overlay';
    el.innerHTML = '<div id="bj-modal-inner"></div>';
    el.addEventListener('click', function(e) {
      if (e.target === el) tutupModal();
    });
    document.body.appendChild(el);
  }

  function bukaOverlay(html) {
    buatOverlay();
    document.getElementById('bj-modal-inner').innerHTML = html;
    document.getElementById('bj-overlay').classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function tutupModal() {
    const el = document.getElementById('bj-overlay');
    if (el) el.classList.remove('open');
    document.body.style.overflow = '';
  }

  // Modal Konfirmasi Pembayaran
  window.bukaModalKonfirmasi = function(url, nomor, nominal, nama) {
    bukaOverlay(`
      <div class="bj-modal">
        <button class="bj-close-x" onclick="tutupModal()">×</button>
        <div class="bj-modal-icon">✅</div>
        <div class="bj-modal-title">Konfirmasi Pembayaran</div>
        <div class="bj-modal-sub">Pastikan dana sudah masuk sebelum konfirmasi</div>
        <div class="bj-info-row"><span>No. Pesanan</span><span>#${nomor}</span></div>
        <div class="bj-info-row"><span>Nama Penerima</span><span>${nama}</span></div>
        <div class="bj-info-total"><span>Total</span><span>${nominal}</span></div>
        <div class="bj-btn-row">
          <button class="bj-btn bj-btn-cancel" onclick="tutupModal()">Batal</button>
          <button class="bj-btn bj-btn-confirm" onclick="aksiBayar('${url}')">✓ Ya, Konfirmasi</button>
        </div>
      </div>
    `);
  };

  // Modal Kirim
  window.bukaModalKirim = function(url, nomor) {
    bukaOverlay(`
      <div class="bj-modal">
        <button class="bj-close-x" onclick="tutupModal()">×</button>
        <div class="bj-modal-icon">🚚</div>
        <div class="bj-modal-title">Tandai Pesanan Dikirim</div>
        <div class="bj-modal-sub">Pesanan <strong>#${nomor}</strong> akan ditandai sebagai <strong>Sedang Dikirim</strong>.</div>
        <div class="bj-btn-row">
          <button class="bj-btn bj-btn-cancel" onclick="tutupModal()">Batal</button>
          <button class="bj-btn bj-btn-kirim" onclick="aksiBayar('${url}')">🚚 Ya, Tandai Dikirim</button>
        </div>
      </div>
    `);
  };

  // Modal Selesai
  window.bukaModalSelesai = function(url, nomor) {
    bukaOverlay(`
      <div class="bj-modal">
        <button class="bj-close-x" onclick="tutupModal()">×</button>
        <div class="bj-modal-icon">🎉</div>
        <div class="bj-modal-title">Tandai Pesanan Selesai</div>
        <div class="bj-modal-sub">Pesanan <strong>#${nomor}</strong> akan ditandai sebagai <strong>Selesai</strong>.</div>
        <div class="bj-btn-row">
          <button class="bj-btn bj-btn-cancel" onclick="tutupModal()">Batal</button>
          <button class="bj-btn bj-btn-selesai" onclick="aksiBayar('${url}')">✅ Ya, Selesaikan</button>
        </div>
      </div>
    `);
  };

  // Modal Lihat Bukti Bayar
  window.lihatBukti = function(url, nomor) {
    bukaOverlay(`
      <div class="bj-modal bj-img-modal">
        <button class="bj-close-x" style="color:white" onclick="tutupModal()">×</button>
        <div class="bj-img-title">📎 Bukti Pembayaran #${nomor}</div>
        <img src="${url}" alt="Bukti Bayar">
        <div class="bj-btn-row" style="margin-top:.75rem">
          <button class="bj-btn bj-btn-close" onclick="tutupModal()">Tutup</button>
          <a href="${url}" download target="_blank"
             style="flex:1;padding:11px;background:#C17F24;color:white;border-radius:10px;
             font-size:14px;font-weight:600;text-align:center;text-decoration:none">
            📥 Unduh
          </a>
        </div>
      </div>
    `);
  };

  // Aksi submit ke URL via POST (bukan GET)
  window.aksiBayar = function(url) {
    const btn = document.querySelector('.bj-btn-confirm, .bj-btn-kirim, .bj-btn-selesai');
    if (btn) { btn.disabled = true; btn.textContent = 'Memproses...'; }
    const csrf = document.cookie.split(';')
      .map(c => c.trim()).find(c => c.startsWith('csrftoken='));
    const csrfToken = csrf ? csrf.split('=')[1] : '';
    fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: ''
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        window.location.reload();
      } else {
        alert('Gagal: ' + (data.error || 'Terjadi kesalahan'));
        if (btn) { btn.disabled = false; btn.textContent = btn.textContent.replace('Memproses...', 'Coba Lagi'); }
      }
    })
    .catch(() => {
      alert('Terjadi kesalahan jaringan, coba lagi.');
      if (btn) { btn.disabled = false; }
    });
  };

  // tutupModal global
  window.tutupModal = tutupModal;

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') tutupModal();
  });
})();