# Roadmap Menuju Professional App

Roadmap ini mengarahkan evolusi proyek EV Dx38 / Dynacord DSP244 dari prototipe web controller menjadi aplikasi yang andal, aman, dapat diuji, dan siap digunakan operator. Prioritas utama adalah kebenaran komunikasi dengan perangkat dan keselamatan kontrol; penambahan fitur dan pemolesan UI mengikuti setelah fondasi tersebut terverifikasi.

## Sasaran Produk

- Mengontrol Dx38/DSP244 dengan status perangkat yang akurat dan dapat dipahami operator.
- Tetap berguna dalam mode demo tanpa perangkat fisik.
- Memisahkan antarmuka, layanan aplikasi, protokol, dan transport serial agar dapat diuji serta dipelihara.
- Memberikan konfigurasi, dokumentasi operasi, diagnostik, dan proses rilis yang jelas.
- Mendukung akses jaringan hanya melalui konfigurasi yang disengaja dan sesuai skenario penggunaan.

## Prinsip dan Batasan

1. Jangan menganggap perintah protokol valid hanya karena ditemukan dalam binary atau dokumentasi; verifikasi pada perangkat nyata.
2. Jangan menampilkan operasi sebagai berhasil sebelum perangkat mengonfirmasi atau kebijakan optimistik dijelaskan secara eksplisit.
3. Tolak nilai dan payload yang tidak valid sebelum membentuk perintah serial.
4. Pertahankan fungsi kontrol yang sudah ada selama refaktor; perubahan perilaku harus punya tes.
5. Bedakan fakta yang sudah diuji, hasil reverse engineering, dan asumsi yang belum dikonfirmasi.

## Fase 1 — Kebutuhan dan Verifikasi Protokol

**Tujuan:** Membuat ruang lingkup dan dasar kebenaran teknis yang dapat ditinjau.

- Tentukan skenario target: aplikasi lokal Windows, akses browser dari LAN, atau keduanya.
- Tetapkan model perangkat, firmware, serial settings, Device ID, fitur yang dijanjikan, dan siapa yang boleh mengoperasikan kontrol.
- Buat matriks fitur: nilai/rentang yang diizinkan, query/set command, respons yang diharapkan, status verifikasi, dan prosedur uji.
- Uji perintah baca/tulis pada perangkat nyata, termasuk kontrol level, mute, preset, EQ, crossover, delay, compressor, limiter, dan metering.
- Tandai perintah yang belum tervalidasi; jangan mengirim beberapa variasi perintah sebagai fallback tanpa bukti bahwa itu aman.

**Kriteria selesai:** Ruang lingkup rilis awal disetujui dan setiap kontrol yang masuk rilis punya perintah serta rentang yang telah diverifikasi atau diberi label eksperimental.

## Fase 2 — Komunikasi Serial yang Andal

**Tujuan:** Mencegah kegagalan I/O atau respons ambigu berubah menjadi state yang keliru.

- Pindahkan driver serial ke modul tersendiri dengan interface transport yang dapat diimplementasikan oleh serial fisik dan simulator.
- Validasi hasil operasi Win32, jumlah byte yang ditulis/dibaca, timeout, encoding, dan framing respons.
- Serialisasikan transaksi melalui satu antrean/worker; tetapkan timeout, batas antrean, dan kebijakan saat perintah gagal.
- Implementasikan status koneksi dan reconnect dengan backoff, bukan hanya mencoba berulang dengan interval tetap.
- Sediakan pengaturan COM port, baud rate, Device ID, serta mode demo; validasi konfigurasi saat aplikasi mulai.
- Tambahkan logging diagnostik untuk koneksi dan transaksi tanpa mencatat data yang tidak perlu.

**Kriteria selesai:** Simulasi timeout, respons parsial, error I/O, unplug, dan reconnect menghasilkan status yang benar tanpa membuat thread atau antrean macet.

## Fase 3 — Backend dan Model State

**Tujuan:** Memisahkan tanggung jawab dan membuat perubahan state terprediksi.

- Pecah aplikasi menjadi modul konfigurasi, protokol, transport, layanan kontrol/state, route API, dan frontend.
- Buat satu sumber kebenaran untuk state perangkat dan lindungi akses konkuren dari request web serta worker serial.
- Bedakan nilai aktual perangkat, nilai yang diminta operator, dan status pending/error untuk operasi yang belum terkonfirmasi.
- Validasi JSON, channel, enum, tipe numerik, batas nilai, serta field wajib pada semua endpoint.
- Gunakan respons error API yang konsisten dengan kode/status yang sesuai; jangan menelan exception komunikasi tanpa melaporkannya.
- Tambahkan endpoint health/status yang memisahkan kesehatan aplikasi, koneksi serial, dan sinkronisasi perangkat.

**Kriteria selesai:** Route API tidak dapat mengirim nilai di luar spesifikasi dan kegagalan kontrol terlihat dengan jelas pada respons serta state.

## Fase 4 — Test Otomatis dan Simulator

**Tujuan:** Memungkinkan pengembangan tanpa perangkat fisik dan menjaga perilaku lama.

- Tambahkan unit test untuk parsing respons, pemetaan nilai, framing, validasi, serta generasi perintah.
- Buat fake/simulator serial dengan respons normal, respons malformed, respons lambat, timeout, dan disconnect yang dapat dikontrol oleh tes.
- Tambahkan tes API untuk operasi sukses, payload salah, channel/enum tidak valid, dan kondisi offline.
- Tambahkan tes integrasi dengan perangkat nyata untuk setiap fitur yang akan dirilis; simpan prosedur dan hasilnya.
- Jalankan tes deterministik sebagai gerbang perubahan sebelum rilis.

**Kriteria selesai:** Seluruh tes tanpa hardware dapat berjalan berulang kali dengan hasil konsisten; daftar fitur yang masih memerlukan verifikasi hardware terdokumentasi.

## Fase 5 — Keamanan dan Operasional

**Tujuan:** Mengurangi risiko kontrol tanpa izin dan membuat aplikasi aman dijalankan.

- Pilih bind address yang aman secara default; jangan membuka server ke seluruh antarmuka tanpa pilihan operator yang eksplisit.
- Dokumentasikan paparan jaringan dan firewall. Jika LAN diperlukan, sediakan kontrol akses yang sesuai dengan skenario deployment.
- Lindungi endpoint kontrol dari request lintas situs yang tidak diinginkan dengan pemeriksaan origin/CSRF yang sesuai.
- Batasi ukuran request dan frekuensi perintah, terutama untuk aksi yang dapat memengaruhi keluaran audio.
- Pastikan shutdown menutup worker serta port serial dengan bersih dan tidak menjalankan server development untuk penggunaan produksi.
- Jelaskan perilaku offline, reconnect, serta tindakan operator saat status perangkat tidak diketahui.

**Kriteria selesai:** Konfigurasi jaringan dan akses terdokumentasi, kontrol tidak terbuka secara tidak sengaja, dan shutdown/restart tidak meninggalkan port dalam keadaan terkunci.

## Fase 6 — Frontend Siap Operator

**Tujuan:** Menyajikan keadaan aktual secara jelas dan mendukung operasi yang cepat serta aman.

- Pisahkan HTML, CSS, dan JavaScript dari string besar di modul backend.
- Tampilkan status koneksi aktual, waktu pembaruan terakhir, sinkronisasi, operasi pending, dan pesan error yang dapat ditindaklanjuti.
- Tangani error jaringan, reconnect, respons API gagal, dan state yang belum dikonfirmasi tanpa menyamarkannya sebagai sukses.
- Tinjau interval polling dan gunakan mekanisme update yang sesuai dengan kebutuhan metering dan beban perangkat.
- Uji penggunaan desktop, tablet, dan ponsel; pastikan kontrol utama seperti mute mudah ditemukan dan tidak mudah terpicu tanpa sengaja.
- Periksa kontras, fokus keyboard, label kontrol, dan ukuran target sentuh.

**Kriteria selesai:** Operator dapat membedakan nilai aktual dari nilai pending/error dan dapat mengenali kondisi perangkat offline dengan cepat.

## Fase 7 — Dokumentasi dan Rilis

**Tujuan:** Membuat instalasi dan pemakaian dapat diulang oleh orang lain.

- Perbarui README untuk instalasi, konfigurasi, menjalankan demo, menghubungkan hardware, dan troubleshooting.
- Sediakan panduan operator terpisah dari dokumentasi protokol/reverse engineering.
- Dokumentasikan matriks kompatibilitas perangkat/firmware, batas parameter, fitur terverifikasi, dan fitur eksperimental.
- Buat checklist rilis yang mencakup tes otomatis, uji hardware, konfigurasi aman, prosedur pemulihan, dan catatan perubahan.
- Lakukan rollout bertahap: simulator/demo, hardware lab, pemakaian terbatas, lalu rilis stabil.

**Kriteria selesai:** Pengguna baru dapat memasang dan menjalankan aplikasi mengikuti dokumentasi, dan setiap rilis memiliki catatan versi serta hasil verifikasi.

## Prioritas Implementasi

1. Verifikasi protokol dan rentang parameter pada perangkat nyata.
2. Serial transport tangguh, antrean transaksi, dan simulator.
3. Validasi API serta model state yang mencerminkan konfirmasi perangkat.
4. Tes otomatis untuk protokol dan API.
5. Keamanan akses jaringan dan lifecycle aplikasi.
6. Pemisahan frontend/backend dan peningkatan UX operator.
7. Panduan operasi serta proses rilis.

## Definisi Selesai untuk Rilis Awal

- Kontrol yang dirilis telah diverifikasi pada perangkat/fimware yang didukung.
- Aplikasi tidak mengklaim perangkat online atau perubahan berhasil tanpa dasar yang benar.
- Input invalid ditolak tanpa mengirim perintah serial.
- Tes unit/API menggunakan simulator lulus; uji hardware untuk fitur rilis tercatat.
- Mode demo dan mode hardware dapat dibedakan dengan jelas.
- Konfigurasi jaringan, instalasi, operasi, dan troubleshooting didokumentasikan.
