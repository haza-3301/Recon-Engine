# core/report_generator.py
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from jinja2 import Environment, FileSystemLoader, TemplateNotFound
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

BASE_DIR = Path(__file__).parent.parent.resolve()

def generate_burp_content(data: Dict[str, Any]) -> str:
    """Menghasilkan daftar subdomain (hostnames) untuk Burp Suite Target Scope."""
    subdomains = data.get("subdomains", {}).keys()
    if not subdomains:
        logging.warning("[BURP EXPORT] Tidak ada subdomain untuk diekspor.")
        return ""
    return "\n".join(sorted(subdomains))

def generate_gnmap_content(data: Dict[str, Any]) -> str:
    """Menghasilkan konten format target list untuk Nmap (-iL)."""
    results_dict = data.get("subdomains", {})
    lines = []
    
    has_ips = any(details.get("ips") for details in results_dict.values())
    if not has_ips:
        logging.warning("[GNMAP EXPORT] Tidak ada data IP untuk diekspor. Gunakan --resolve-ip.")
        return "\n".join(sorted(results_dict.keys()))

    for domain, details in sorted(results_dict.items()):
        ips = details.get("ips")
        if ips:
            for ip_info in ips:
                ip_addr = ip_info.get("address")
                lines.append(f"{ip_addr}\t{domain}")
        else:
            lines.append(domain)
            
    return "\n".join(lines)

def generate_html_content(data: Dict[str, Any], domain: str, template_path: Optional[Path] = None) -> str:
    """
    Menghasilkan laporan HTML dari data hasil pemindaian menggunakan template Jinja2.
    Mendukung template default dan template kustom yang disediakan pengguna.
    """
    if not JINJA2_AVAILABLE:
        error_msg = "[HTML EXPORT] Pustaka 'Jinja2' tidak ditemukan. Tidak dapat membuat laporan HTML."
        logging.error(error_msg)
        return f"<h1>Error</h1><p>{error_msg} Please run: <code>pip install Jinja2</code></p>"

    try:
        if template_path:
            # Jika template kustom diberikan, gunakan direktori parent-nya sebagai loader path
            if not template_path.exists():
                raise FileNotFoundError(f"File template kustom tidak ditemukan di: {template_path}")
            template_dir = template_path.parent
            template_name = template_path.name
            env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
        else:
            # Gunakan template default
            template_dir = BASE_DIR / 'templates'
            template_name = 'report.html.j2'
            env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
        
        template = env.get_template(template_name)

    except TemplateNotFound:
        error_msg = f"[HTML EXPORT] Template '{template_name}' tidak ditemukan di direktori '{template_dir}'."
        logging.error(error_msg)
        return f"<h1>Error</h1><p>{error_msg}</p>"
    except Exception as e:
        error_msg = f"[HTML EXPORT] Gagal memuat template HTML: {e}"
        logging.error(error_msg, exc_info=True)
        return f"<h1>Error</h1><p>{error_msg}</p>"

    context = {
        "domain": domain,
        "subdomains": data.get("subdomains", {}),
        "contributions": data.get("contributions", {}),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB")
    }
    
    return template.render(context)