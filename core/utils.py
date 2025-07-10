# core/utils.py
import ipaddress
import re

def is_valid_domain(domain: str) -> bool:
    """
    Memvalidasi format domain, menolak IP, dan memvalidasi TLD.
    """
    if not domain or len(domain) > 253:
        return False

    # Tolak jika input adalah alamat IP
    try:
        ipaddress.ip_address(domain)
        return False
    except ValueError:
        pass

    # Handle Internationalized Domain Names (IDN)
    try:
        encoded_domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return False
        
    # Pola regex untuk label domain dan domain secara keseluruhan
    label_re = r"(?!-)[a-zA-Z0-9-]{1,63}(?<!-)"
    general_domain_re = rf"^({label_re}\.)+{label_re}$"
    if not re.match(general_domain_re, encoded_domain):
        return False
        
    # Validasi Top-Level Domain (TLD)
    tld = encoded_domain.split('.')[-1]
    if len(tld) < 2:
        return False
        
    # TLD tidak boleh sepenuhnya angka kecuali ini adalah Punycode
    if not tld.lower().startswith('xn--') and any(char.isdigit() for char in tld) and all(char.isdigit() for char in tld):
        return False
            
    return True

def normalize_subdomain(subdomain: str) -> str:
    """
    Membersihkan dan menormalkan nama subdomain.
    Contoh: " *.GOOGLE.com " -> "google.com"
    """
    return subdomain.lower().strip().lstrip("*.")