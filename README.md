# ParamFinderPy

ParamFinderPy adalah tool Python sederhana untuk mencari nama parameter dari sebuah domain atau URL. Tool ini melakukan crawling ringan pada link internal lalu mengumpulkan parameter dari:

- Query URL, contoh `?id=1&search=test`
- Field form HTML, contoh `name="email"`
- Pola sederhana pada teks atau JavaScript jika opsi `--javascript` diaktifkan

Gunakan hanya pada website yang Anda miliki atau punya izin untuk diuji.

## Fitur

- Crawling link internal dengan batas `depth` dan `max-urls`
- Deteksi parameter dari URL
- Deteksi parameter dari form HTML
- Deteksi parameter sederhana dari JavaScript/teks
- Output teks atau JSON
- Simpan daftar parameter unik ke file
- Opsi mengikuti subdomain
- Tanpa dependency eksternal, cukup Python 3

## Struktur

```text
ParamFinderPy/
├── param_finder.py
└── README.md
```

## Cara Menjalankan

Masuk ke folder tool:

```bash
cd /home/kali/ParamFinderPy
```

Jalankan scan dasar:

```bash
python3 param_finder.py https://example.com
```

Jika target ditulis tanpa skema, tool akan memakai HTTPS secara otomatis:

```bash
python3 param_finder.py example.com
```

## Contoh Penggunaan

Crawl lebih dalam:

```bash
python3 param_finder.py https://example.com --depth 3 --max-urls 300
```

Simpan parameter unik ke file:

```bash
python3 param_finder.py https://example.com --save params.txt
```

Output JSON:

```bash
python3 param_finder.py https://example.com --json
```

Cari pola parameter di JavaScript atau teks halaman:

```bash
python3 param_finder.py https://example.com --javascript
```

Ikuti subdomain:

```bash
python3 param_finder.py https://example.com --include-subdomains
```

Atur delay dan timeout:

```bash
python3 param_finder.py https://example.com --delay 0.5 --timeout 15
```

Gabungan opsi:

```bash
python3 param_finder.py https://example.com --depth 3 --max-urls 300 --javascript --save params.txt
```

## Opsi

| Opsi | Default | Keterangan |
| --- | --- | --- |
| `target` | wajib | Domain atau URL target |
| `--depth` | `2` | Kedalaman crawl link internal |
| `--max-urls` | `100` | Batas maksimal URL yang dikunjungi |
| `--delay` | `0.25` | Jeda antar request dalam detik |
| `--timeout` | `10` | Timeout request dalam detik |
| `--include-subdomains` | mati | Ikuti subdomain dari domain target |
| `--javascript` | mati | Cari pola parameter sederhana di teks/JavaScript |
| `--json` | mati | Tampilkan output dalam format JSON |
| `--save` | kosong | Simpan nama parameter unik ke file |

## Contoh Output

```text
Target       : https://example.com/
URL dikunjungi: 12
Parameter    : 4

Daftar parameter:
- id [url]
  https://example.com/product?id=1
- email [form]
  form POST https://example.com/contact dari https://example.com/contact
- search [url, form]
  https://example.com/search?search=test
```

## Output JSON

Dengan opsi `--json`, hasil berisi:

- `target`: URL awal
- `visited`: daftar URL yang berhasil dikunjungi
- `parameter_count`: jumlah nama parameter unik
- `parameters`: detail parameter dan sumbernya
- `errors`: error ringan selama crawl

## Catatan Penting

ParamFinderPy hanya mencari nama parameter. Tool ini tidak mengeksploitasi parameter, tidak melakukan brute force, dan tidak mengirim payload berbahaya. Hasilnya cocok dipakai sebagai langkah awal audit, misalnya untuk membuat daftar parameter yang akan diverifikasi manual.
