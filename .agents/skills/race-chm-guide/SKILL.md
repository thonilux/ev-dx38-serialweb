---
name: race-chm-guide
description: >-
  Knowledge base and operational guide extracted from RACE.chm (Electro-Voice / Dynacord Dx38 RACE software).
  Covers software architecture, RS-485 / RS-232 communication, project configuration, Setup vs Live modes,
  firmware update procedures, and decompilation techniques for CHM files.
---

# RACE (Electro-Voice / Dynacord Dx38) Knowledge & CHM Reference

Panduan ini berisi rangkuman komprehensif dari dokumentasi bantuan [RACE.chm](file:///d:/son/re-race/RACE.chm) untuk software **RACE** (Remote Control software untuk digital sound processor Electro-Voice Dx38 / Dynacord DSP244), serta cara inspeksi/dekompilasi file CHM menggunakan utility bawaan Windows (`hh.exe`).

---

## 1. Cara Membuka & Dekompilasi File CHM via `hh.exe`

File `.chm` adalah Compiled HTML Help file. Windows menyertakan tool CLI bawaan `hh.exe` di `%SystemRoot%\hh.exe`.

### A. Membuka Viewer GUI
```powershell
hh.exe "D:\son\re-race\RACE.chm"
```
*Catatan:* Jika jendela CHM terbuka tetapi halaman kosong ("Navigation to the webpage was canceled"), hilangkan proteksi file (Unblock) terlebih dahulu:
```powershell
Unblock-File -Path "D:\son\re-race\RACE.chm"
```

### B. Dekompilasi CHM Menjadi Dokumen HTML Mentah
Untuk merekayasa balik (reverse-engineering), membaca teks utuh, atau mengekstrak gambar dan stylesheet:
```powershell
hh.exe -decompile "D:\son\re-race\extracted_chm" "D:\son\re-race\RACE.chm"
```
File-file utama yang dihasilkan:
- `*.htm`: File halaman bantuan masing-masing bab/fitur.
- `RACE.hhc`: Sitemap / Table of Contents (daftar isi tree-view).
- `RACE.hhk`: Index keyword sitemap.
- `pics/`: Aset visual / diagram tangkapan layar UI.
- `IRIS.CSS`: Stylesheet presentasi help.

---

## 2. Struktur & Fitur Utama RACE Software (Dx38 DSP)

### A. Arsitektur Komunikasi Hardware (RS-232 & RS-485)
- **Protokol Bus:**
  - Menggunakan komunikasi serial RS-232 atau bus multi-drop RS-485.
  - Maksimal panjang kabel RS-485: **1200 meter**.
  - Menggunakan converter USB-to-RS485 atau RS232-to-RS485.
- **Konfigurasi COM Port:**
  - Menu: `Remote` > `RS-485 Setup` / `RS-232 Setup`.
  - Konfigurasi serial disimpan di **Windows Registry** (tidak hilang saat project ditutup).
- **Pengalamatan Device:**
  - Tiap unit fisik Dx38 / DSP244 pada bus RS-485 wajib memiliki **Device ID / Address yang unik**.
  - Software RACE secara otomatis mengalokasikan Device ID di project PC, yang harus dicocokkan dengan ID di unit perangkat fisik.

### B. Alur Going Online & Discovery (Netscan)
1. **Online Dengan Project:**
   - Masuk via menu `Remote`.
   - RACE memvalidasi kesesuaian unit di PC dengan unit di bus.
   - User memilih apakah akan push setting dari PC ke perangkat (*Write to units*) atau membaca dari perangkat.
2. **Online Tanpa Project (Netscan Otomatis):**
   - Menu: `Remote` > `RS-485 Remote`.
   - RACE menjalankan fungsi **Netscan** untuk mendeteksi semua perangkat yang aktif di bus RS-485.
   - Tabel discovery akan menampilkan daftar perangkat yang terdeteksi, lalu RACE menarik setting dari perangkat ke PC (*Read from units*).
3. **Troubleshooting Perangkat Tidak Terdeteksi:**
   - Perangkat dalam kondisi mati (power off).
   - Masalah wiring / konektor RS-485 kabel putus/terbalik polaritas (A/B).
   - Jarak kabel melebihi batas 1200m.
   - Terdapat **ID konflik** (dua atau lebih unit memiliki RS-485 Device ID yang sama).

### C. Mode Operasi: Setup Mode vs Live Mode
| Parameter / Fitur | Setup Mode | Live Mode |
| :--- | :--- | :--- |
| **Tujuan** | Konfigurasi sistem penuh | Pengoperasian saat pertunjukan/live |
| **Editing Parameter** | Menambah/menghapus device, alokasi Device & Group ID, edit DSP parameter real-time | Hanya kontrol Level dan Mute |
| **Keamanan** | Dapat dikunci dengan password (`Password` > `Set Password for Setup Mode`) | Tidak memerlukan password setup |
| **Aliran Data** | Satu arah dari PC ke unit (*flow of data is only from PC to unit*) | Status meter VU dipantau secara real-time |
| **Metering** | VU meter menampilkan device yang dipilih (tanda bar hijau di sebelah kiri) | VU meter menampilkan status Limiter dan Compressor aktif |

### D. Fitur Grouping
- Mendukung hingga **12 Group ID**.
- Memungkinkan kontrol parameter secara paralel (multiple devices yang masuk dalam satu group akan mengikuti setting parameter yang sama).

### E. Manajemen File Project
- **Format File:** File project RACE berekstensi `*.x38` (RACE 1.xx, 2.xx, hingga 3.xx).
- **Kompatibilitas Mundur:** Project lama dari versi 1.xx / 2.xx dapat diimpor ke RACE 3.xx via `File` > `Open Project` (filter `*.x38`).
- **Peringatan Kompatibilitas Maju:** File yang disimpan dengan RACE versi 3.00+ **tidak dapat dibuka** oleh RACE versi lawas (< 3.00).
- **Project Info:** Menu `Window` > `Project Info` menyimpan metadata proyek (Venue, Customer, Engineer, Date, dll.).

### F. Pembaruan Firmware (Firmware Update)
- Mendukung pembaruan firmware unit DSP (Dx38 / DSP244).
- **Syarat RS-485 Update:** Unit harus sudah memiliki minimal firmware **v2.00**. Jika di bawah v2.00, wajib update via serial **RS-232**.
- Lokasi file firmware bawaan: folder `RACE/os/`.
- Selama transfer firmware berlangsung, layar display LCD pada unit fisik akan kosong/blank hingga proses selesai.
- Selesai flashing, RACE otomatis menjalankan netscan ulang untuk mengonfirmasi versi firmware baru.

---

## 3. Implikasi Reverse Engineering (`RACE.exe`)

Berdasarkan dokumentasi bantuan ini, saat menganalisis binary `RACE.exe`, titik fokus RE mencakup:
1. **Komunikasi Serial / Registry:**
   - Panggilan Win32 API serial: `CreateFileA("COMx")`, `SetCommState`, `BuildCommDCB`, `ReadFile`, `WriteFile`.
   - Registry key tempat menyimpan konfigurasi COM: Cari registry path (biasanya di bawah `HKEY_CURRENT_USER\Software\...` atau `HKEY_LOCAL_MACHINE\Software\...`).
2. **Format Paket RS-485:**
   - Algoritma framing, checksum, dan penanganan ID perangkat (1-byte address, header, payload perintah DSP, VU meter stream).
3. **Password Protection:**
   - Pemeriksaan password untuk "Setup Mode" (algoritma hashing atau plain compare yang disimpan di dalam file `.x38`).
4. **Format File Project (`*.x38`):**
   - Struktur header file binary `.x38`, pemetaan parameter DSP (EQ, Delay, Crossover, Limiter, Compressor).
