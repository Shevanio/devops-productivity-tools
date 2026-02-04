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
Analyze Docker images for size optimization and basic vulnerabilities.

**Features:**
- Layer-by-layer size breakdown
- Identify large files/directories
- Suggest optimization opportunities
- Basic CVE scanning
- Compare image versions
- Export reports

**Usage:**
```bash
docker-analyzer --image nginx:latest
docker-analyzer --image myapp:v1.2 --compare myapp:v1.1
docker-analyzer --image node:18 --export report.json
```

**Status:** 📋 Planned

---

### 3. **Log Parser** (`log-parser`)
Extract insights from log files (nginx, systemd, application logs).

**Features:**
- Pattern-based error extraction
- Common log format parsers (nginx, Apache, JSON logs)
- Statistics and summaries
- Time-based filtering
- Export to JSON/CSV
- Real-time log monitoring

**Usage:**
```bash
log-parser --file /var/log/nginx/access.log --errors-only
log-parser --file app.log --pattern "ERROR|CRITICAL" --last 1h
log-parser --file syslog --stats --export stats.json
```

**Status:** 📋 Planned

---

### 4. **Environment File Manager** (`env-manager`)
Securely manage environment variables across different environments.

**Features:**
- Encrypt/decrypt .env files
- Switch between environments (dev, staging, prod)
- Validate required variables
- Template support
- Git-friendly (encrypted files can be committed)
- Diff between environments

**Usage:**
```bash
env-manager encrypt .env.prod --output .env.prod.enc
env-manager decrypt .env.prod.enc
env-manager switch staging
env-manager validate --template .env.example
env-manager diff dev prod
```

**Status:** 📋 Planned

---

### 5. **Backup Automator** (`backup-auto`)
Simple, reliable backup solution with incremental backups and rotation.

**Features:**
- Incremental backups
- Configurable retention policies
- Multiple destinations (local, S3, SFTP)
- Compression (gzip, zstd)
- Backup verification
- Restore functionality
- Email notifications

**Usage:**
```bash
backup-auto --source /var/www --dest /backups/www --incremental
backup-auto --config backup-config.yaml --run
backup-auto restore --backup /backups/www/2024-02-04.tar.gz --dest /var/www
backup-auto list --dest /backups/www
```

**Status:** 📋 Planned

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
git clone https://github.com/YOUR_USERNAME/devops-productivity-tools.git
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

- [x] Project setup and structure
- [ ] Git Branch Cleaner MVP (Phase 1)
- [ ] Docker Analyzer MVP (Phase 1)
- [ ] Log Parser MVP (Phase 2)
- [ ] Env Manager MVP (Phase 2)
- [ ] Backup Automator MVP (Phase 2)
- [ ] Integration testing suite
- [ ] CI/CD pipeline
- [ ] Published pip package
- [ ] GUI wrapper (optional, Phase 3)

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
