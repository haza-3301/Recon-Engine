# Recon Engine

![Build](https://img.shields.io/badge/test-passing-brightgreen)
![Stars](https://img.shields.io/github/stars/haza-3301/Recon-Engine/?style=social)
![Last Update](https://img.shields.io/github/last-commit/haza-3301/Recon-Engine/)
![Issues](https://img.shields.io/github/issues/haza-3301/Recon-Engine/)
![License](https://img.shields.io/github/license/haza-3301/Recon-Engine/)


> **Reliability & Hardening Edition v6.8**
> Fast, modular, and extensible subdomain enumeration engine for bug bounty hunters and pentesters.

---

## 🚀 Overview

**Recon Engine** is a powerful, asynchronous, and plugin-based subdomain enumeration tool. Designed for high reliability, real-world reconnaissance, and flexible integration, it supports both API and CLI-based plugins, caching, live progress UI, and robust output management.

---

## ✨ Features

* 🔌 **Plugin System**: Supports API and tool-based plugins (`plugins/api/`, `plugins/tools/`)
* ⚡ **Async + Threaded**: Combines asyncio + threading for max performance
* 📦 **Caching**: Encrypted result caching with validation & locking
* 🧪 **Validation**: Strict DNS & format validation to ensure clean results
* 🖥️ **Rich UI**: Beautiful CLI interface with live progress (Rich-powered)
* 📤 **Output Options**: Save to `.txt`, `.json`, `.csv` formats
* 🛠️ **Resilient**: Retry mechanism, timeout controls, and fault-tolerant by design

---

## 🛠 Requirements

* Python 3.8+
* Dependencies (auto-installed via `pip install -r requirements.txt`):

  * `httpx`, `rich`, `filelock`, `dnspython`

---

## 🔧 Installation

```bash
# Clone the repository
$ git clone https://github.com/Haza-3301/Recon-Engine.git
$ cd Recon-Engine

# Install dependencies
$ pip install -r requirements.txt
```

---

## 🧪 Usage

### Basic Recon

```bash
$ python recon_engine.py -d example.com
```

### 📸 Cuplikan Penggunaan

![Recon Sample](/images/image-1.png)

![Installer Output](/images/image-3.png)

### Scan Multiple Domains

```bash
$ python recon_engine.py -i domains.txt
```

### Output to File

```bash
$ python recon_engine.py -d example.com -o results/example.json
```

### List Available Plugins

```bash
$ python recon_engine.py --list-plugins
```

### Select or Exclude Plugins

```bash
$ python recon_engine.py -d example.com --use-plugins subfinder,findomain
$ python recon_engine.py -d example.com --exclude-plugins hackertarget
```

---

## 📂 Output

Results are stored in your chosen format and path, with optional `%d` placeholder for domain names.

* `.txt` : Simple newline list
* `.json` : Structured JSON
* `.csv` : With headers for integration

---

## 📁 Project Structure

```
Recon-Engine/
├── recon_engine.py      # Main engine
├── plugins/             # Plugin folders
│   ├── api/
│   └── tools/
├── ui/
│   └── live_progress.py
├── requirements.txt
└── README.md
```

---

## 📄 License

MIT License - see [LICENSE](./LICENSE)

---

## 🤝 Contributing

Coming soon! Plugin contributions are welcome in `plugins/tools/` or `plugins/api/`.

---

## 👨‍💻 Author

**Haza-3301**
Bug bounty hunter & Python toolsmith
GitHub: [@Haza-3301](https://github.com/Haza-3301)

---

## 🧠 Disclaimer

This tool is intended for **authorized security testing** and **educational purposes** only.
Misuse of this tool is strictly prohibited.

---

## 🌐 Stay Updated

Follow the project or watch the repo to get updates when new versions or plugins are released!
