# Recon-Engine

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/github/license/haza-3301/Recon-Engine)
![Version](https://img.shields.io/badge/version-9.0.0-green)

> Framework modular dan asinkron untuk enumerasi subdomain — dirancang untuk bug bounty, pentest, dan recon cepat.

---

## Fitur Utama

- **Modular & extensible** — plugin API dan CLI tool tanpa mengubah core
- **Asynchronous** — semua sumber data berjalan paralel (`asyncio` + `httpx`)
- **Live progress CLI** — tabel status real-time (`rich`)
- **Output multi-format** — TXT, CSV, JSON, Burp, Nmap gnmap, HTML
- **Result cache** — JSON + SHA256 checksum + file lock (bukan enkripsi)
- **Validasi domain** — filter otomatis + dukungan IDN/Punycode
- **Typed plugin contract** — `BaseAPIPlugin` / `BaseToolPlugin` (v9)

---

## Instalasi

```bash
git clone https://github.com/haza-3301/Recon-Engine.git
cd Recon-Engine
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Opsional: installer tools eksternal (subfinder, findomain, dll.)
python install.py install
```

---

## Pemakaian

```bash
# Default: full pipeline → recon.txt (satu file, tanpa artefak perantara)
python3 recon.py padang.go.id -t 300

# Output ke path lain
python3 recon.py padang.go.id -t 300 -o hasil/recon.txt

# Live hostnames saja (enum + filter + dnsx + httpx probe, tanpa fingerprint)
python3 recon.py padang.go.id -t 300 --enum-only
```

| Mode | Pipeline | Isi `recon.txt` |
|------|----------|-----------------|
| **default** | enum → filter → dnsx → httpx (fingerprint) | URL + status, title, IP — **tanpa [FAILED]** |
| **`--enum-only`** | enum → filter → dnsx → httpx (`-silent`) | Hostname live bersih |

Tidak ada `raw.txt`, `subs.txt`, `dnsx.txt`, atau `live.txt` di disk — semua stage di memory.

---

## Binary (`tools_bin/`)

Portable — path relatif root repo, tanpa hardcode user/direktori lokal.

| File | Fungsi |
|------|--------|
| `pd-httpx` | ProjectDiscovery httpx |
| `dnsx` | ProjectDiscovery dnsx |

```bash
python3 install.py install          # unduh dari GitHub ke tools_bin/
python3 recon.py example.com --show-tools

# Opsional: salin dari direktori Anda sendiri
python3 install.py sync-tools /path/to/bin
```

---

## Arsitektur v9

```
main.py (CLI)
    │
    ├── core/config.py        ReconConfig (dataclass)
    ├── core/cache.py         CacheManager
    ├── core/orchestrator.py  ReconOrchestrator — async plugin runner
    ├── core/plugin_loader.py Discovery + lint
    ├── core/base_plugin.py   BaseAPIPlugin / BaseToolPlugin
    ├── core/output_writer.py Multi-format export
    └── plugins/
            ├── api/          HTTP sources
            └── tools/        CLI wrappers
```

**Alur:**

```
Input domain → load plugins → [cache hit?] → ReconOrchestrator.gather()
    → validasi & dedup → [resolve IP / ASN] → write_output → cache write
```

---

## Plugin Bawaan

| Plugin | Tipe | Sumber | Catatan |
|--------|------|--------|---------|
| crt.sh | API | Certificate transparency | — |
| CertSpotter | API | certspotter.com | — |
| AlienVault OTX | API | Passive DNS | — |
| HackerTarget | API | hostsearch | Plain text (`is_json=False`) |
| Chaos | API | ProjectDiscovery | Env `CHAOS_KEY` |
| subfinder | Tool | ProjectDiscovery | PATH / `tools_bin/` |
| assetfinder | Tool | tomnomnom | Go binary |
| findomain | Tool | Findomain | Binary |
| Wayback | Built-in | web.archive.org | Flag `--wayback` |

---

## Menambah Plugin

### API (`plugins/api/myplugin.py`)

```python
from typing import Any, Set
from core.base_plugin import BaseAPIPlugin

class Plugin(BaseAPIPlugin):
    def __init__(self):
        self.name = "My API"
        self.url = "https://api.example.com/subdomains/{domain}"
        self.api_key_env = "MY_API_KEY"  # opsional

    def parse(self, data: Any) -> Set[str]:
        if not isinstance(data, dict):
            return set()
        return set(data.get("hosts", []))
```

### Tool (`plugins/tools/mytool.py`)

```python
from typing import List
from core.base_plugin import BaseToolPlugin

class Plugin(BaseToolPlugin):
    def __init__(self):
        self.name = "mytool"

    def get_command(self, domain: str) -> List[str]:
        return ["mytool", "-d", domain]
```

Validasi: `python3 main.py --lint-plugins`

---

## Output

| Format | Flag | Isi |
|--------|------|-----|
| `.txt` | `-o out.txt` | Subdomain (+ IP/ASN) |
| `.json` | `-o out.json` | Nested dict |
| `.csv` | `-o out.csv` | subdomain, ip, asn, org |
| `.burp` | `-o out.burp` | Hostname list |
| `.gnmap` | `-o out.gnmap` | Nmap target list |
| `.html` | `-o out.html` | Laporan Jinja2 |

---

## Pengembangan

```bash
pip install -r requirements.txt
pytest plugins/tests -v
python3 main.py --lint-plugins
```

Struktur test: `plugins/tests/`

---

## Kontribusi

Lihat [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Lisensi

MIT — lihat [LICENSE](LICENSE).
