# Standar Penulisan Kode & Kontribusi Recon-Engine

Panduan ini WAJIB diikuti oleh seluruh kontributor pada proyek ini untuk menjaga keamanan, konsistensi, dan robustness.

---

## 1. Struktur Plugin

### Plugin API (`plugins/api/`)
- Harus memiliki `class Plugin` dengan atribut: `name`, `url`, serta method `parse`.
- Tidak boleh menggunakan `eval`, `exec`, atau dynamic import.
- Parsing defensif: selalu cek tipe dan struktur data sebelum diproses.
- Tidak menerima input selain dari core engine (domain yang tervalidasi).
- **Contoh:**
    ```python
    class Plugin:
        name = "Example"
        url = "https://api.example.com/{domain}"

        def parse(self, data):
            if not isinstance(data, dict) or "subdomains" not in data:
                logging.warning(f"[{self.name}] Response tidak valid.")
                return set()
            return set(data["subdomains"])
    ```

### Plugin Tools (`plugins/tools/`)
- Harus memiliki `class Plugin` dengan atribut: `name`, dan method `get_command`.
- Method `get_command` harus mengembalikan **list** (bukan string) untuk subprocess.
- Tidak boleh menggunakan `shell=True` pada subprocess.
- Tidak menerima flag dinamis dari user tanpa validasi.
- **Contoh:**
    ```python
    class Plugin:
        name = "ToolX"

        def get_command(self, domain):
            return ["toolx", "-d", domain]
    ```

---

## 2. Penulisan Kode Core

- Tidak boleh ada `eval`, `exec`, atau dynamic import tanpa validasi.
- Path output selalu divalidasi agar tidak keluar dari working directory.
- Cegah overwrite file tanpa flag `--overwrite`.
- Gunakan logging, jangan silent fail.
- Jika dynamic import, validasi atribut/plugin yang dimuat.
- Fitur baru harus defensif terhadap input eksternal dan robust error handling.

---

## 3. Logging & Error Handling

- Gunakan modul `logging` untuk warning dan error.
- Plugin harus logging jika parsing gagal atau data tidak valid.
- Jangan gunakan print untuk error pada kode inti.

---

## 4. Testing

- Tulis unit test untuk fungsi parsing plugin API (kasus valid & invalid).
- Pastikan plugin tool hanya menjalankan command yang sudah tervalidasi.

---

## 5. Standar Style

- Ikuti **PEP8** dan gunakan formatter seperti `black`/`isort`.
- Tambahkan komentar/docstring pada fungsi publik dan method utama plugin.
- Nama file plugin: lowercase, snake_case.

---

## 6. Review & Pull Request

- Jangan merge tanpa minimal satu review.
- Sertakan contoh output/result plugin pada PR (boleh di comment).
- Jika menambah dependensi, update `requirements.txt`.

---

## 7. Keamanan

- Jangan pernah:
    - Menulis file ke luar working directory (kecuali disetujui maintainer).
    - Mengambil input user sebagai argument command tanpa validasi.
    - Menambah plugin dengan shell injection, dynamic code execution, atau trust pada data luar.

---

## 8. Contoh Pelanggaran

- Menggunakan `os.system`, `subprocess.call` dengan string command.
- Mengeksekusi/eval response API tanpa validasi.
- Menulis file output ke `/tmp`, `/etc`, atau path absolut tanpa validasi.

---

## 9. Kontak & Diskusi

Untuk pertanyaan atau diskusi, gunakan [GitHub Issue](https://github.com/haza-3301/Recon-Engine/issues) atau hubungi maintainer.

---

**Terima kasih sudah berkontribusi secara aman dan konsisten!**
