# core/ip_resolver.py
import asyncio
import json
import logging
import ipaddress
from pathlib import Path
from typing import Dict, List, Set, Any

import httpx

try:
    import dns.asyncresolver
    from dns.exception import DNSException
    DNSPYTHON_AVAILABLE = True
except ImportError:
    DNSPYTHON_AVAILABLE = False

# --- Konfigurasi Resolver DNS ---
if DNSPYTHON_AVAILABLE:
    resolver = dns.asyncresolver.Resolver()
    resolver.nameservers = ['8.8.8.8', '1.1.1.1'] # Menggunakan resolver publik yang andal
    resolver.timeout = 5
    resolver.lifetime = 5

# --- Konfigurasi Cache ASN ---
CACHE_DIR = Path.home() / ".recon_engine_cache"
CACHE_DIR.mkdir(exist_ok=True)
ASN_CACHE_FILE = CACHE_DIR / "asn_cache.json"

def _load_asn_cache() -> Dict[str, Dict]:
    """Memuat cache ASN dari file."""
    if not ASN_CACHE_FILE.exists():
        return {}
    try:
        with ASN_CACHE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        logging.warning("[RESOLVER] Gagal memuat cache ASN, file mungkin rusak.")
        return {}

def _save_asn_cache(cache: Dict[str, Dict]):
    """Menyimpan cache ASN ke file."""
    try:
        with ASN_CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        logging.warning(f"[RESOLVER] Gagal menyimpan cache ASN: {e}")

async def resolve_domains_to_ips(subdomains: Set[str]) -> Dict[str, List[str]]:
    """
    Melakukan resolusi DNS secara asinkron untuk sekumpulan subdomain.

    Args:
        subdomains: Set berisi nama subdomain yang akan di-resolve.

    Returns:
        Sebuah dictionary yang memetakan setiap subdomain ke daftar alamat IP-nya.
        Jika resolusi gagal, daftar IP akan kosong.
    """
    if not DNSPYTHON_AVAILABLE:
        logging.warning("[RESOLVER] Pustaka 'dnspython' tidak ditemukan. Resolusi IP dilewati.")
        return {domain: [] for domain in subdomains}

    tasks = {domain: resolver.resolve(domain, 'A') for domain in subdomains}
    results = await asyncio.gather(*[v for v in tasks.values()], return_exceptions=True)
    
    ip_map: Dict[str, List[str]] = {}
    domain_list = list(subdomains)

    for i, res in enumerate(results):
        domain = domain_list[i]
        if isinstance(res, dns.resolver.Answer):
            ip_map[domain] = sorted([item.to_text() for item in res])
        else:
            # Log jika ada error spesifik selain 'NoAnswer' atau 'NXDOMAIN'
            if not isinstance(res, (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN)):
                logging.debug(f"[RESOLVER] Gagal me-resolve {domain}: {res}")
            ip_map[domain] = [] # Tetap masukkan domain dengan list kosong
            
    return ip_map

async def lookup_ips_asn(ips: Set[str]) -> Dict[str, Dict[str, Any]]:
    """
    Mencari informasi ASN untuk sekumpulan alamat IP menggunakan ip-api.com.
    Hasil dari API akan di-cache untuk mengurangi panggilan berulang.
    """
    asn_info_map: Dict[str, Dict[str, Any]] = {}
    ips_to_query = set()
    
    # Muat cache dan cek IP mana yang perlu di-query
    asn_cache = _load_asn_cache()
    for ip in ips:
        if ip in asn_cache:
            asn_info_map[ip] = asn_cache[ip]
        else:
            # Hanya query IP publik, abaikan IP privat
            try:
                if ipaddress.ip_address(ip).is_global:
                    ips_to_query.add(ip)
            except ValueError:
                logging.debug(f"[RESOLVER] Format IP tidak valid, dilewati: {ip}")


    if not ips_to_query:
        return asn_info_map

    logging.info(f"[RESOLVER] Mencari info ASN untuk [green]{len(ips_to_query)}[/green] IP baru...")
    
    # API ip-api.com mendukung batch hingga 100 IP per request
    ip_chunks = [list(ips_to_query)[i:i + 100] for i in range(0, len(ips_to_query), 100)]
    
    async with httpx.AsyncClient() as client:
        tasks = []
        for chunk in ip_chunks:
            # API membutuhkan body JSON
            task = client.post("http://ip-api.com/batch?fields=query,status,message,as,org", json=chunk)
            tasks.append(task)
            
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    for res in responses:
        if isinstance(res, httpx.Response):
            if res.status_code == 200:
                try:
                    data = res.json()
                    for item in data:
                        ip = item.get("query")
                        if item.get("status") == "success":
                            info = {
                                "asn": item.get("as", "N/A"),
                                "org": item.get("org", "N/A")
                            }
                            asn_info_map[ip] = info
                            asn_cache[ip] = info # Tambahkan ke cache
                        else:
                            # Tandai sebagai gagal agar tidak di-query lagi sesi ini
                            asn_info_map[ip] = {"error": item.get("message", "Unknown error")}
                except json.JSONDecodeError:
                    logging.warning("[RESOLVER] Gagal mem-parsing respons ASN dari API.")
            else:
                logging.error(f"[RESOLVER] API ASN mengembalikan status {res.status_code}. Respons: {res.text}")
        elif isinstance(res, httpx.RequestError):
            logging.error(f"[RESOLVER] Gagal menghubungi API ASN: {res}")

    _save_asn_cache(asn_cache)
    return asn_info_map