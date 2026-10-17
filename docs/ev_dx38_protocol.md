# Dokumentasi Protokol Komunikasi Serial EV Dx38 / Dynacord DSP244

Berdasarkan hasil sniffing langsung dari komunikasi aktif `RACE.exe` dengan unit fisik EV Dx38 (Firmware: EV DX38 V3.21).

---

## 1. Parameter Serial Port
- **Baudrate:** 19200 bps (default) / 9600 bps
- **Data Bits:** 8
- **Parity:** None
- **Stop Bits:** 1 (8-N-1)
- **Flow Control:** None
- **Format:** Plain Text ASCII (diakhiri dengan newline `\r` atau `\r\n`)

---

## 2. Struktur Perintah (Command Structure)
Semua perintah diawali dengan prefiks Device ID target: `/ID<DeviceID>/`

### A. Device Info & Query
- **Tanya Info Device:**
  - Kirim: `/ID1/DEVICE ?\r`
  - Respon: `/ID1/DEVICE EV DX38 V3.21\r`

### B. Mute Control (Per Channel & Master)
- **Mute ON Channel 1:**
  - Kirim: `/ID1/Out1/Mute 1\r`
- **Mute OFF Channel 1 (Unmute):**
  - Kirim: `/ID1/Out1/Mute 0\r`
- **Pola Output Lain:**
  - `/ID1/Out2/Mute <0|1>`
  - `/ID1/Out3/Mute <0|1>`
  - `/ID1/Out4/Mute <0|1>`

### C. Live VU Metering Query
- **Polling Meter:**
  - Kirim: `/ID1/VU ?\r`
  - Respon: `VU@@@@@@pp\r`
  - *Karakter '@' bernilai 0x40 (menandakan level sinyal nol / noise floor)*.
  - *Karakter 'pp' menandakan bitmask status Limiter & Compressor*.

---

## 3. Perintah Lanjutan Lainnya (Dari Ekstraksi Binary RACE.exe)
- **Level / Gain Fader:**
  - `/ID1/CONTROL/OUT<ch>/LEVEL <nilai>`
- **Preset Recall:**
  - `/ID1/CONFIGURATION/USERMEMORY <preset_num>`
