# core/output_writer.py
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.report_generator import (generate_burp_content, generate_gnmap_content,
                                   generate_html_content)

# Coba impor Rich untuk tampilan yang lebih baik
try:
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

CONSOLE = Console(color_system="auto") if RICH_AVAILABLE else None

def _flatten_results(data: Dict[str, Dict]) -> List[Dict]:
    """Mengubah data bertingkat menjadi list flat untuk CSV."""
    flat_list = []
    for domain, details in data.items():
        ips = details.get("ips")
        if not ips:
            # Tambahkan baris bahkan jika tidak ada IP, untuk konsistensi
            flat_list.append({"subdomain": domain, "ip": "", "asn": "", "org": ""})
        else:
            for ip_info in ips:
                asn_data = ip_info.get("asn_info", {})
                flat_list.append({
                    "subdomain": domain,
                    "ip": ip_info.get("address", ""),
                    "asn": asn_data.get("asn", ""),
                    "org": asn_data.get("org", "")
                })
    return flat_list

def _write_txt(file_path: Path, data: Dict[str, Dict]):
    """Menulis data ke file teks biasa, termasuk IP dan ASN jika ada."""
    lines = []
    for domain, details in sorted(data.items()):
        ips = details.get("ips")
        if not ips:
            lines.append(domain)
            continue
        
        # Jika ada IP, buat satu baris per IP untuk kejelasan
        for ip_info in ips:
            ip_addr = ip_info.get('address')
            asn_info = ip_info.get('asn_info')
            line = f"{domain} [{ip_addr}]"
            if asn_info and 'error' not in asn_info:
                line += f" [{asn_info.get('asn', 'N/A')}, {asn_info.get('org', 'N/A')}]"
            lines.append(line)
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def _write_json(file_path: Path, data: Dict[str, Dict]):
    """Menulis data ke file format JSON."""
    file_path.write_text(json.dumps(data, indent=4, sort_keys=True), encoding="utf-8")

def _write_csv(file_path: Path, data: Dict[str, Dict]):
    """Menulis data ke file format CSV dengan kolom IP dan ASN."""
    flat_data = _flatten_results(data)
    if not flat_data:
        return

    headers = ["subdomain", "ip", "asn", "org"]
    with file_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(flat_data)

def _write_burp(file_path: Path, data: Dict[str, Any]):
    """Menghasilkan file target untuk Burp Suite."""
    content = generate_burp_content(data)
    file_path.write_text(content + "\n", encoding="utf-8")

def _write_gnmap(file_path: Path, data: Dict[str, Any]):
    """Menghasilkan file target list untuk Nmap."""
    content = generate_gnmap_content(data)
    file_path.write_text(content + "\n", encoding="utf-8")

def _write_html(file_path: Path, data: Dict[str, Any], domain: str, template_path: Optional[Path]):
    """Menghasilkan file laporan HTML."""
    content = generate_html_content(data, domain, template_path)
    file_path.write_text(content, encoding="utf-8")

def write_output(domain: str, results: Dict[str, Any], args: Any):
    """
    Fungsi abstraksi utama untuk memproses dan menulis hasil ke file.
    Sekarang menerima 'args' untuk akses ke semua opsi output.
    """
    output_path_str = args.output
    total_domains = args.total_domains
    domain_index = args.domain_index
    
    # Periksa apakah ada output path yang diberikan
    if not output_path_str:
        return

    processed_results = results.get("subdomains", {})
    # Beberapa format (seperti HTML) mungkin ingin ditulis bahkan jika tidak ada hasil
    if not processed_results and not (output_path_str.endswith('.html')):
         logging.warning(f"[WRITER] Tidak ada subdomain untuk ditulis untuk domain '{domain}'. File tidak dibuat.")
         return

    # Logika penanganan multi-domain
    if '%' not in output_path_str and total_domains > 1:
        p = Path(output_path_str)
        output_path_str = str(p.with_name(f"{p.stem}-{domain_index}{p.suffix}"))
    
    output_path = Path(output_path_str.replace('%d', domain))

    # --- Validasi Keamanan Path ---
    try:
        resolved_path = output_path.resolve()
        cwd = Path.cwd().resolve()
        if not str(resolved_path).startswith(str(cwd)):
            logging.error(f"[WRITER] [bold red]SECURITY[/bold red]: Path output [yellow]'{output_path}'[/yellow] berada di luar direktori kerja. Penulisan dibatalkan.")
            return
    except Exception as e:
        logging.error(f"[WRITER] Path output tidak valid: '{output_path}'. Error: {e}")
        return

    # --- Cek Penimpaan File ---
    if output_path.exists() and not args.overwrite:
        logging.warning(f"[WRITER] File output [yellow]{output_path}[/] sudah ada. Gunakan --overwrite untuk menimpa.")
        return
    
    # --- Pemilihan Format dan Penulisan ---
    ext = output_path.suffix.lower().strip('.')
    writers = {
        'txt': _write_txt,
        'json': _write_json,
        'csv': _write_csv,
        'burp': _write_burp,
        'gnmap': _write_gnmap,
        'html': _write_html,
    }

    writer_func = writers.get(ext)
    
    if not writer_func:
        logging.warning(f"[WRITER] Format '{ext}' tidak dikenali. Menyimpan sebagai teks biasa (.txt).")
        output_path = output_path.with_suffix('.txt')
        writer_func = _write_txt

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Sesuaikan pemanggilan berdasarkan kebutuhan fungsi writer
        if ext == 'html':
            # Teruskan path template kustom jika ada
            writer_func(output_path, results, domain, args.html_template)
        elif ext in ['burp', 'gnmap']:
            writer_func(output_path, results)
        else:
            # Writer lama hanya butuh data subdomain yang sudah diproses
            writer_func(output_path, processed_results)
            
        logging.info(f"[WRITER] Hasil untuk domain '{domain}' disimpan ke [cyan]{output_path}[/]")
    except Exception as e:
        logging.error(f"[WRITER] Gagal menulis file output {output_path}: {e}", exc_info=True)