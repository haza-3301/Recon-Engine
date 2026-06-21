# Bundled CLI binaries (ProjectDiscovery)

Binary disimpan di folder ini agar pipeline memanggil path absolut
relatif terhadap root repo — tanpa path user/machine hardcoded.

| File | Tool |
|------|------|
| `pd-httpx` | ProjectDiscovery httpx (bukan `pip install httpx`) |
| `dnsx` | ProjectDiscovery dnsx |

## Install (semua platform)

```bash
python install.py install
```

Mengunduh `pd-httpx` dan `dnsx` dari GitHub releases ke folder ini.

## Salin dari direktori lain (opsional)

```bash
export HEPH_TOOLS=/path/to/your/bin
python install.py sync-tools

# atau
python install.py sync-tools /path/to/your/bin
```
