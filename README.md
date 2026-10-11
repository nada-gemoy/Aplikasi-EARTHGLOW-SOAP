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

1. Install dependensi:
   ```
   pip install -r requirements.txt
   ```

2. Jalankan aplikasi:
   ```
   python main.py
   ```

## Laporan Keuangan dan Ekspor Excel

Dashboard memisahkan **Transaksi Langsung** dari **Pesanan Online**. Keduanya
memiliki form pencatatan berdasarkan produk, nama pemesan, jumlah, pembayaran,
dan status; pesanan online juga mewajibkan alamat pengiriman. Stok diperbarui
otomatis saat transaksi dicatat. Daftar dan ringkasan pembukuan tiap saluran
ditampilkan terpisah. Data transaksi dari versi lama belum menyimpan saluran;
agar tidak hilang, data lama tetap ditampilkan di daftar pesanan online.
Tabel transaksi, retur, dan laporan disusun sebagai kartu data dua kolom yang
mengikuti lebar layar ponsel, sehingga tidak perlu menggeser halaman ke kanan
untuk membaca kolom.

Buka tombol dashboard **RETUR BARANG** untuk melihat transaksi dan riwayat
retur; tekan **PROSES RETUR** pada transaksi lunas yang dipilih. Isi jumlah
barang retur dan keluhan, lalu pilih **Uang kembali** atau **Kirim pengganti**
beserta produk penggantinya. Nilai retur, uang kembali, biaya/kerugian,
serta laba yang berkurang dicatat. Barang retur menambah stok otomatis dan
barang pengganti mengurangi stok otomatis.

Isi HPP (biaya modal per barang) pada form Kelola Produk. HPP disimpan bersama
transaksi saat penjualan dicatat, sehingga perubahan HPP produk berikutnya
tidak mengubah laba transaksi lama. Transaksi lama yang belum memiliki data HPP
ditandai tanpa HPP; labanya tidak dihitung seolah-olah modalnya nol.

Pada menu **Laporan Keuangan**, pilih **EKSPOR EXCEL**. Berkas `.xlsx`
disimpan di folder `Downloads` dengan lembar Ringkasan, Transaksi, dan Retur.
Rumus Excel menghitung omzet, HPP, laba, dan nilai retur terpisah untuk
transaksi langsung serta pesanan online. Excel menghitung ulang saat berkas
dibuka. Laba yang ditampilkan adalah laba kotor (omzet dikurangi HPP), belum
dikurangi biaya operasional lain.

## Alur Pesanan dan Pembayaran (Mode Simulasi)

Pesanan online dicatat manual dengan memilih platform, produk, pelanggan,
alamat, dan catatan. Pesanan dimulai dengan status **Baru** dan pembayaran
**Sudah Dibayar (Online)**. Kasir dapat mengubah status secara berurutan:
**Baru → Diproses → Siap → Lunas**. Saat pesanan diselesaikan, aplikasi
menampilkan pratinjau struk/label simulasi. Pesanan baru ditandai pada tombol
Pesanan Online di dashboard.

Pembelian langsung dibuka melalui layar kasir. Produk dipilih manual dari
katalog, lalu jumlah dan total belanja dihitung. Pembayaran **Cash**
memvalidasi uang diterima dan menghitung kembalian. Pilihan **QRIS** membuka
konfirmasi pembayaran simulasi dengan total tagihan; kasir menekan
**Simulasikan berhasil** untuk menyelesaikan transaksi.

Mode ini belum terhubung ke GoFood, GrabFood, ShopeeFood, DANA, ShopeePay,
gateway pembayaran, dapur, kurir, pemindai barcode, atau printer. QRIS simulasi
tidak menampilkan kode yang dapat dipindai; struk dan label hanya pratinjau di
layar.

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
