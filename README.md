# EarthGlow Soap - Aplikasi Toko Sabun

Projek Tahap 1: **Navigasi & Event Handling**
Dibuat dengan **Python + Kivy**, berdasarkan rancangan UI/UX di Figma.

## Struktur Navigasi

```
Welcome → Create Account → Login → Profile → Search → Shop
                                                          ↓
                                    Cart  ←  Detail Produk
```

Setiap perpindahan layar (screen) dipicu oleh **event tombol** (on_release),
sesuai materi Navigation & Event Handling.

## Struktur File

```
earthglow_soap/
├── main.py          # Logika aplikasi & event handling tiap screen
├── navigasi.kv       # Layout/tampilan tiap screen
└── README.md
```

## Cara Menjalankan

1. Install Kivy terlebih dahulu:
   ```
   pip install kivy
   ```

2. Jalankan aplikasi:
   ```
   python main.py
   ```

## Cara Mengembangkan Lebih Lanjut

- Tambahkan gambar produk asli di folder `assets/` lalu tampilkan dengan widget `Image` di `navigasi.kv`.
- Ganti data `PRODUCTS` di `main.py` dengan data dari file/database.
- Tambahkan validasi login yang sesungguhnya di `LoginScreen.do_login()`.

## Panduan Push ke GitHub (sesuai instruksi tugas)

```bash
# 1. Inisialisasi repository baru (khusus projek ini, jangan gabung dgn repo latihan)
git init
git add .
git commit -m "Initial commit: navigasi dasar EarthGlow Soap"

# 2. Hubungkan ke repository GitHub baru
git remote add origin https://github.com/username/earthglow-soap.git
git branch -M main
git push -u origin main
```

Setiap kali menambah fitur baru, buat commit baru dengan nama sesuai fitur, contoh:
```bash
git add .
git commit -m "Menambahkan halaman Search dan kategori produk"
git push
```

Kirim link repository ke Google Classroom agar bisa dicek oleh pengajar.
