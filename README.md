# Recon Engine v8.0.0 🚀 

[![Last Commit](https://img.shields.io/github/last-commit/haza-3301/Recon-Engine)](https://github.com/haza-3301/Recon-Engine/commits/main) [![Issues](https://img.shields.io/github/issues/haza-3301/Recon-Engine)](https://github.com/haza-3301/Recon-Engine/issues)

[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/downloads/) [![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT) 

[![Release](https://img.shields.io/github/v/release/haza-3301/Recon-Engine?color=orange)](https://github.com/haza-3301/Recon-Engine/releases) [![Stars](https://img.shields.io/github/stars/haza-3301/Recon-Engine?style=social)](https://github.com/haza-3301/Recon-Engine)

&#x20;&#x20;

---

**Recon Engine** adalah kerangka kerja enumerasi subdomain modular, cepat, dan dapat diperluas. Dirancang untuk efisiensi dan fleksibilitas, Recon Engine dapat menjalankan berbagai plugin API dan tool eksternal secara asinkron untuk mengumpulkan subdomain, memperkaya hasil dengan resolusi IP dan ASN, serta menghasilkan output dalam format standar industri seperti Nmap, Burp Suite, dan laporan HTML.

---

## 🔥 Fitur Unggulan

* **Eksekusi Asinkron Penuh** menggunakan `asyncio`
* **Sistem Plugin Modular**: Tambahkan plugin API atau tools eksternal tanpa ubah core
* **Resolusi IP & ASN Lookup**:

  * `--resolve-ip`: Resolusi DNS dengan `dns.asyncresolver`
  * `--asn-lookup`: ASN & info organisasi via `ipinfo.io`, `ip-api.com`, atau `bgp.tools`
* **Ekspor Format Pentest**:

  * `.txt`, `.csv`, `.json`, `.gnmap`, `.burp`, dan `.html`
* **Laporan HTML Profesional** dengan `Jinja2`
* **Cache Cerdas** dengan validasi checksum
* **UI CLI Interaktif** (menggunakan `rich`)
* **Keamanan Output Path** dan validasi domain ketat

---

## 📁 Struktur Proyek

```
recon_engine/
├── main.py
├── requirements.txt
├── README.md
├── core/
│   ├── error_handler.py
│   ├── ip_resolver.py
│   ├── output_writer.py
│   ├── plugin_loader.py
│   ├── report_generator.py
│   └── utils.py
├── plugins/
│   ├── api/
│   │   └── example_api.py
│   └── tools/
│       └── example_tool.py
├── templates/
│   └── report.html.j2
└── ui/
    └── live_progress.py
```

---

## 🚀 Instalasi

```bash
# 1. Clone repositori
$ git clone https://github.com/user/recon-engine.git
$ cd recon-engine

# 2. Aktifkan virtual environment (disarankan)
$ python3 -m venv venv
$ source venv/bin/activate
# Windows: venv\Scripts\activate

# 3. Install dependensi
$ pip install -r requirements.txt
```

---

## 🔧 Penggunaan Dasar

```bash
# Pemindaian domain sederhana
$ python3 main.py -d example.com

# Resolusi IP dan ASN
$ python3 main.py -d example.com --resolve-ip --asn-lookup

# Ekspor hasil
$ python3 main.py -d example.com -o result.txt       # Plain text
$ python3 main.py -d example.com -o result.csv       # CSV
$ python3 main.py -d example.com -o result.json      # JSON
$ python3 main.py -d example.com -o targets.gnmap    # Format Nmap
$ python3 main.py -d example.com -o scope.burp       # Format Burp
$ python3 main.py -d example.com -o report.html      # HTML

# Gunakan template HTML kustom
$ python3 main.py -d example.com -o out.html --html-template templates/report.html.j2

# Input daftar domain
$ python3 main.py -i list.txt -o output-%d.json

# Lihat plugin yang tersedia
$ python3 main.py --list-plugins
```

---

## 📦 Format Output

| Format   | Tujuan                          | Ekstensi |
| -------- | ------------------------------- | -------- |
| `.txt`   | Daftar subdomain biasa          | `.txt`   |
| `.csv`   | Kompatibel dengan Excel/Sheets  | `.csv`   |
| `.json`  | Parsing otomatis oleh tools     | `.json`  |
| `.gnmap` | Import ke Nmap (-iL)            | `.gnmap` |
| `.burp`  | Scope Burp Suite (Target Scope) | `.burp`  |
| `.html`  | Laporan visual profesional      | `.html`  |

---

## 🔌 Membuat Plugin

### Plugin API

```python
# plugins/api/example_api.py
class Plugin:
    def __init__(self):
        self.name = "Example API"
        self.url = "https://api.example.com/find?domain={domain}"
        # self.api_key_env = "EXAMPLE_API_KEY"  # Opsional

    def parse(self, data):
        subdomains = set()
        # ... parsing logic ...
        return subdomains
```

### Plugin Tool

```python
# plugins/tools/example_tool.py
class Plugin:
    def __init__(self):
        self.name = "exampletool"

    def get_command(self, domain):
        return [self.name, "-d", domain, "--silent"]
```

## 📬 Kontribusi & Dukungan

* 💬 Diskusi & pertanyaan: [GitHub Discussions](https://github.com/user/recon-engine/discussions)
* 🐛 Laporkan bug: [Issues](https://github.com/user/recon-engine/issues)
* ⭐ Beri bintang jika proyek ini bermanfaat!

---

## ⚖️ Lisensi

Recon Engine dirilis di bawah [MIT License](LICENSE).

**Full Changelog**: https://github.com/haza-3301/Recon-Engine/commits/v8.0.0
