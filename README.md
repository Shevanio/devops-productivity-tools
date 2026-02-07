# ⚙️ DevOps & Productivity Tools

> Automate the boring stuff. A curated collection of CLI tools to streamline your development workflow and DevOps tasks.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🎯 Philosophy

**"If you do it more than twice, automate it."**

These tools are designed to:
- ✅ Save time on repetitive tasks
- ✅ Reduce human error
- ✅ Improve consistency across environments
- ✅ Be simple, fast, and reliable

---

## 🛠️ Available Tools

### 1. **Git Branch Cleaner** (`git-cleaner`)
Clean up merged branches automatically with safety checks.

**Features:**
- List all merged branches (local/remote)
- Interactive deletion with confirmation
- Filter by date, author, or pattern
- Automatic backup before deletion
- Dry-run mode
- Exclude protected branches (main, develop, master)

**Usage:**
```bash
# Interactive cleanup
git-cleaner

# Dry run to see what would be deleted
git-cleaner --dry-run

# Delete branches older than 60 days
git-cleaner --older-than 60

# Include remote branches
git-cleaner --remote --dry-run
```

**Status:** 🚧 In Development (MVP)

---

### 2. **Docker Image Analyzer** (`docker-analyzer`)
Analyze Docker images for size optimization and layer breakdown.

**Features:**
- Layer-by-layer size breakdown with visual bars
- Identify largest layers and commands
- Optimization suggestions (base image, cache cleanup, layer count)
- Compare image versions side-by-side
- Pull images automatically
- Multiple output formats (rich, JSON)
- APT/npm cache detection
- Self-signed certificate detection

**Usage:**
```bash
# Analyze an image
docker-analyzer --image nginx:latest

# Compare two versions
docker-analyzer --image myapp:v1.0 --compare myapp:v2.0

# Pull and analyze
docker-analyzer --image python:3.11-alpine --pull

# Show optimization suggestions
docker-analyzer --image myapp:latest --suggestions

# JSON output
docker-analyzer --image nginx --output json
```

**Status:** 🚧 Complete (MVP)

---

### 3. **Log Parser** (`log-parser`)
Extract insights from log files with multiple format support.

**Features:**
- Multiple format parsers (nginx, Apache, JSON, syslog, Python, Docker)
- Auto-format detection
- Level-based filtering (ERROR, WARNING, INFO, etc.)
- Pattern matching with regex
- Time-range filtering (--since, --until, --last)
- Statistics and summaries (level distribution, top errors, timeline)
- Visual charts and tables
- Multiple output formats (table, JSON)
- Errors-only mode

**Usage:**
```bash
# Parse and show stats
log-parser /var/log/nginx/access.log --stats

# Show only errors
log-parser app.log --errors-only

# Filter by level
log-parser app.log --level ERROR --level CRITICAL

# Filter by pattern
log-parser app.log --pattern "database.*error"

# Last hour
log-parser app.log --last 1h

# Time range
log-parser app.log --since "2024-01-01 10:00:00" --until "2024-01-01 12:00:00"

# JSON output
log-parser app.log --output json > report.json
```

**Status:** 🚧 Complete (MVP)

---

### 4. **Environment File Manager** (`env-manager`)
Securely manage environment variables across different environments.

**Features:**
- Encrypt/decrypt .env files with password-based encryption
- PBKDF2 key derivation with 100,000 iterations
- AES encryption (Fernet symmetric encryption)
- Git-friendly (encrypted files can be committed safely)
- View encrypted files without decrypting
- Validation support
- Secure password input (hidden)

**Usage:**
```bash
# Encrypt .env file
env-manager encrypt .env.prod

# Decrypt to stdout
env-manager decrypt .env.prod.enc

# Decrypt to file
env-manager decrypt .env.prod.enc --output .env.prod

# View without decrypting
env-manager view .env.prod.enc
```

**Status:** ✅ Complete

---

### 5. **Backup Automator** (`backup-auto`)
Simple, reliable backup solution with incremental backups and rotation.

**Features:**
- Full and incremental backup support
- Multiple compression algorithms (gzip, bzip2, xz, none)
- Retention policies (by days or max count)
- SHA256 integrity verification
- Metadata tracking for each backup
- Exclusion patterns (like .gitignore)
- Restore functionality
- Backup listing and verification
- Local filesystem destination

**Usage:**
```bash
# Create full backup
backup-auto create /var/www /backups/www

# Incremental backup with custom compression
backup-auto create /var/www /backups/www --type incremental --compression xz

# With exclusions
backup-auto create /home/user /backups/home --exclude "*.log" --exclude "node_modules"

# Restore backup
backup-auto restore /backups/www/backup_full_20240204_120000.tar.gz /var/www

# Verify backup integrity
backup-auto verify /backups/www/backup_full_20240204_120000.tar.gz

# List all backups
backup-auto list /backups/www
```

**Status:** ✅ Complete

---

## 🚀 Installation

### Prerequisites
- Python 3.9 or higher
- pip
- Git (for git-cleaner)
- Docker (for docker-analyzer)

### Install from source

```bash
# Clone the repository
git clone https://github.com/Shevanio/devops-productivity-tools.git
cd devops-productivity-tools

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### Install via pip (future)

```bash
pip install devops-productivity-tools
```

---

## 📖 Documentation

Detailed documentation for each tool is available in the [`docs/`](docs/) directory:

- [Git Branch Cleaner Guide](docs/git-cleaner.md)
- [Docker Image Analyzer Guide](docs/docker-analyzer.md)
- [Log Parser Guide](docs/log-parser.md)
- [Environment File Manager Guide](docs/env-manager.md)
- [Backup Automator Guide](docs/backup-automator.md)

---

## 🧪 Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tools --cov-report=html

# Run specific tool tests
pytest tests/test_git_cleaner.py -v
```

### Code Quality

```bash
# Format code
black .

# Lint
ruff check .

# Type checking
mypy tools/
```

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

### Quick Start for Contributors

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-tool`)
3. Make your changes
4. Add tests (coverage must be >70%)
5. Run quality checks (`black .`, `pytest`, `ruff check .`)
6. Commit (`git commit -m 'Add new tool'`)
7. Push (`git push origin feature/new-tool`)
8. Open a Pull Request

---

## 💡 Tool Suggestions

Have an idea for a new productivity tool? Open an issue with the `enhancement` label!

**Criteria for new tools:**
- Solves a real, recurring problem
- Can't be easily done with existing standard tools
- Fits the DevOps/productivity theme
- Can be implemented reliably

---

## 📊 Project Roadmap

- [x] Project setup and structure ✅
- [x] Git Branch Cleaner MVP ✅
- [x] Docker Analyzer MVP ✅
- [x] Log Parser MVP ✅
- [x] Env Manager MVP ✅
- [x] Backup Automator MVP ✅
- [ ] Integration testing suite
- [ ] Published pip package
- [ ] GUI wrapper (optional, Phase 3)

**🎉 All 5 core tools complete! (100%)**

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Inspired by the Unix philosophy: "Do one thing well"
- Built for developers, by developers
- Community-driven improvements

---

## 📧 Contact

For questions, issues, or suggestions:
- Open an issue on GitHub
- Join the discussions

**Happy automating!** 🚀
