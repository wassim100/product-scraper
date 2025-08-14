<<<<<<< HEAD
# Selenium Scraper Suite

Production-ready scraping suite for servers, storage, and printers/scanners. It orchestrates Selenium scrapers, optional Gemini-based cleaning, and MySQL storage via a central scheduler.

## Highlights
=======
# Product Scraper – Serveurs, Stockage, Imprimantes & Scanners

Système de scraping automatisé avec post‑traitement IA (Gemini) et insertion MySQL, orchestré par un scheduler unique.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Selenium](https://img.shields.io/badge/Selenium-WebDriver-green.svg)](https://selenium.dev)
[![AI](https://img.shields.io/badge/AI-Gemini-orange.svg)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-red.svg)](LICENSE)
>>>>>>> 2b8329a (feat(epson): add EpsonPrinters and EpsonScanner scrapers; orchestrator DB flow; brand-scoped deactivation flag; README overhaul)

- Central scheduler (filter by categories or scripts)
- Gemini cleaning (optional) with batching and retries
- MySQL upserts with brand-scoped deactivate-missing
- Safe testing flags: headless, max products, deactivate toggle
- Per-script logs and JSON artifacts

<<<<<<< HEAD
## Setup

1) Python 3.11+ (3.12 recommended)
2) pip install -r requirements.txt
3) Create .env with DB creds and GEMINI_API_KEY

## Run via scheduler

- All: python -m automation.scheduler
- Only printers/scanners: set SCHEDULER_CATEGORIES=imprimantes_scanners
- Only Epson scripts: set SCHEDULER_SCRIPTS=EpsonPrinters.py,EpsonScanner.py

Env flags:
- HEADLESS_MODE=true|false (default true)
- ENABLE_DB=true|false (default true)
- ENABLE_AI_CLEANING=true|false (default true)
- ENABLE_DEACTIVATE_MISSING=true|false (default true)
- MAX_PRODUCTS=0 (0 = no limit)
- SCHEDULER_CATEGORIES=serveurs,stockage,imprimantes_scanners
- SCHEDULER_SCRIPTS=comma-separated names
- MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
- GEMINI_API_KEY

## Epson scripts

- imprimantes_scanners/EpsonPrinters.py → epson_printers_scanners_full.json
- imprimantes_scanners/EpsonScanner.py → epson_scanners_full.json

When RUNNING_UNDER_SCHEDULER=true, scrapers skip direct DB writes; the scheduler handles AI + DB.

## Notes

- Logs: logs/ per run
- Selenium: Chrome; keep chromedriver.exe or rely on Selenium Manager
- MySQL: Unique (brand, sku) and (brand, link_hash); lifecycle fields present
- AI cleaning: see ai_processing/gemini_cleaning.py
=======
### 🎯 Extraction multi‑marques
- Serveurs: ASUS, Dell, HP, Lenovo, XFusion
- Stockage: Dell, Lenovo
- Imprimantes & Scanners: Epson (EpsonPrinters + EpsonScanner), HP

### 🔧 Fonctionnalités avancées
- Extraction des spécifications détaillées depuis les pages produits
- Pagination robuste + gestion des popups/cookies
- Nettoyage IA automatique (Gemini) après chaque scraping
- Insertion MySQL avec clés uniques, suivi lifecycle et désactivation des produits non revus
- Orchestrateur unique avec logs par script, timeouts et filtres par catégorie/script

### 🤖 Intelligence Artificielle
- Gemini 1.5: nettoyage/structuration des `tech_specs`
- Fichiers `.cleaned.json` générés puis insérés en base (préférés aux `.json` bruts)

## 🏗️ Structure du projet

```
product-scraper/
│
├── 📁 serveurs/                    # Scrapers serveurs (asus/dell/hp/lenovo/xfusion)
│   ├── asus.py
│   ├── dell.py
│   ├── hp.py
│   ├── lenovo.py
│   └── xfusion.py
│
├── 📁 ai_processing/              # Traitement IA
│   └── gemini_cleaning.py         # Nettoyage Gemini AI
│
├── 📁 database/                   # Base de données
│   ├── config.py                  # Paramètres MySQL
│   ├── mysql_connector.py         # Connecteur + création/migrations simples
│   └── test_mysql.py              # Test de connexion
│
├── 📁 automation/                 # Automatisation
│   └── scheduler.py               # Planificateur de tâches
│
├── 📁 stockage/                   # Scrapers stockage
│   ├── dell.py
│   └── lenovo.py
│
├── 📁 imprimantes_scanners/       # Imprimantes & scanners
│   ├── EpsonPrinters.py           # Epson (imprimantes)
│   ├── EpsonScanner.py            # Epson (scanners)
│   └── hp.py                      # HP
│
├── 📄 main.py                     # Script principal
├── 📄 requirements.txt            # Dépendances Python
├── 📄 README.md                   # Documentation
└── 📄 .gitignore                  # Fichiers à ignorer
```

## 🚀 Installation (Windows)

### 1. **Cloner le repository**
```powershell
git clone https://github.com/wassim100/product-scraper.git
cd product-scraper
```

### 2. **Créer un environnement virtuel**
```powershell
python -m venv venv
venv\Scripts\Activate
```

### 3. **Installer les dépendances**
```powershell
pip install -r requirements.txt
```

### 4. ChromeDriver
- Optionnel: placez `chromedriver.exe` à la racine. Sinon Selenium Manager résoudra automatiquement.
>>>>>>> 2b8329a (feat(epson): add EpsonPrinters and EpsonScanner scrapers; orchestrator DB flow; brand-scoped deactivation flag; README overhaul)

## Troubleshooting

<<<<<<< HEAD
- Script names must match scheduler entries (EpsonPrinters.py, EpsonScanner.py)
- For partial tests: set MAX_PRODUCTS>0 and ENABLE_DEACTIVATE_MISSING=false
- Git: ensure local main tracks origin/main before pushing

## License

MIT
=======
### Orchestrateur (recommandé)
Exécuter tous les scrapers via le scheduler, avec filtres optionnels:

```powershell
# Exécution manuelle unique
$env:HEADLESS_MODE="true"; $env:ENABLE_DB="true"; $env:ENABLE_AI_CLEANING="true"; `
$env:SCHEDULER_CATEGORIES="imprimantes_scanners"; `
$env:SCHEDULER_SCRIPTS="imprimantes_scanners/EpsonPrinters.py,imprimantes_scanners/EpsonScanner.py"; `
python .\main.py --mode schedule --manual-run
```

Flags utiles:
- HEADLESS_MODE=true|false
- ENABLE_DB=true|false (insertion DB par le scheduler)
- ENABLE_AI_CLEANING=true|false (nettoyage Gemini post‑scrape)
- ENABLE_DEACTIVATE_MISSING=true|false (désactivation des produits non revus)
- MAX_PRODUCTS=10 (run réduit de test)
- SCHEDULER_CATEGORIES=serveurs,stockage,imprimantes_scanners
- SCHEDULER_SCRIPTS=chemins,relatifs,aux,scripts

Astuce tests: pour éviter de désactiver des produits lors d’un run réduit (MAX_PRODUCTS>0), définissez `ENABLE_DEACTIVATE_MISSING=false`.

### Exécution directe d’un scraper (développement)
```powershell
python .\imprimantes_scanners\EpsonPrinters.py
python .\imprimantes_scanners\EpsonScanner.py
```

### Traitement IA (manuel)
```powershell
python .\ai_processing\gemini_cleaning.py --in path\to\raw.json --out path\to\cleaned.json
```

## 📦 Données extraites

### **Format JSON Standard**
```json
{
  "brand": "XFusion",
  "category": "AI Servers",
  "name": "FusionServer G5500 V7",
  "link": "https://www.xfusion.com/...",
  "tech_specs": {
    "Form Factor": "4U AI server",
    "Processor": "2 x 4th/5th Gen Intel Xeon Scalable",
    "Memory": "32 x DIMMs up to 5600 MT/s"
  },
  "scraped_at": "2025-07-22T10:43:36.808174",
  "datasheet_link": "https://www.xfusion.com/en/resource/...",
  "image_url": "https://www.xfusion.com/wp-content/uploads/..."
}
```

## 🔧 Configuration

### **Variables d'environnement (.env)**
```env
# API
GEMINI_API_KEY=your_gemini_api_key_here

# MySQL (optionnel si valeurs par défaut)
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=scraping_db

# Scraping / Orchestrateur
HEADLESS_MODE=true
ENABLE_DB=true
ENABLE_AI_CLEANING=true
ENABLE_DEACTIVATE_MISSING=true
MAX_PRODUCTS=0
SCHEDULER_CATEGORIES=
SCHEDULER_SCRIPTS=
```

## 🎯 Détails notables
- Clés uniques DB: (brand, sku) et (brand, link_hash) pour déduplication fiable
- Champs lifecycle: is_active, last_seen + audit IA (ai_processed, ai_processed_at)
- Le scheduler force RUNNING_UNDER_SCHEDULER=1 pour éviter les doubles insertions côté scrapers

## 🧪 Tests & validation
- Validez par runs réduits: `MAX_PRODUCTS=1` + `ENABLE_DEACTIVATE_MISSING=false`
- Consultez les logs par script dans `./logs/` et le rapport JSON d’exécution du scheduler

## 📈 Bonnes pratiques
- Préférez les `.cleaned.json` pour l’insertion DB
- Évitez les runs réduits avec désactivation active
- Placez le dossier sur un chemin court si OneDrive verrouille des fichiers

## 🛠️ Technologies utilisées

- **Python 3.8+**
- **Selenium WebDriver** : Automation web
- **Google Gemini AI** : Nettoyage structuré des spécifications
- **MySQL** : Stockage base de données (optionnel)
- **JSON** : Format de données principal
- **Chrome/Chromium** : Navigateur pour scraping

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit les changements (`git commit -am 'Ajout nouvelle fonctionnalité'`)
4. Push vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer une Pull Request

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🙏 Remerciements

- **Selenium** pour l'automation web
- **Google Gemini AI** pour le traitement intelligent
- **ChromeDriver** pour l'exécution des navigateurs

## 📞 Contact

- **Auteur** : Wassim
- **GitHub** : [wassim100](https://github.com/wassim100)
- **Repository** : [product-scraper](https://github.com/wassim100/product-scraper)

---

⭐ **N'hésitez pas à mettre une étoile si ce projet vous aide !** ⭐
>>>>>>> 2b8329a (feat(epson): add EpsonPrinters and EpsonScanner scrapers; orchestrator DB flow; brand-scoped deactivation flag; README overhaul)
