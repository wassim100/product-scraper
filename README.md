# Product Scraper – Serveurs, Stockage, Imprimantes & Scanners

Système de scraping automatisé (multi‑marques) avec post‑traitement IA (Gemini) et insertion MySQL. Conçu pour être rapide, modulable, et sûr (idempotent). 

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org) [![Selenium](https://img.shields.io/badge/Selenium-WebDriver-green.svg)](https://selenium.dev) [![AI](https://img.shields.io/badge/AI-Gemini-orange.svg)](https://ai.google.dev) [![License](https://img.shields.io/badge/License-MIT-red.svg)](LICENSE)

## 🚀 Principales fonctionnalités
- Orchestrateur central (filtrage par catégories/scripts) + variables d'environnement
- Extraction hybride: tuiles produits (DOM structuré) + JSON‑LD + fallback PDP (enrichissement conditionnel)
- Normalisation IA (Gemini) avec batching, retries, contraintes de format JSON strict
- Upsert MySQL idempotent (clés uniques `(brand, sku)` & `(brand, link_hash)`), désactivation sélective (`ENABLE_DEACTIVATE_MISSING`)
- Flags de performance: `FAST_SCRAPE`, `HEADLESS_MODE`, `MAX_PRODUCTS`, `SKIP_PDP_ENRICH`
- Journalisation par script et artefacts JSON bruts / nettoyés
- CLI base de données (`database/db_cli.py`) pour test, listing, export, statistiques

## 🧩 Périmètre actuel
| Domaine        | Marques / Scripts |
|----------------|-------------------|
| Serveurs       | ASUS, Dell, HP (tile extractor + PDP fallback), Lenovo, XFusion |
| Stockage       | Dell, Lenovo |
| Imprimantes & Scanners | Epson (Printers + Scanner), HP |

## 🏗️ Architecture (vue rapide)
```
ai_processing/        → Nettoyage & politiques Gemini
automation/           → Scheduler / orchestration
database/             → Connexion, schéma, CLI, migrations légères
serveurs/, stockage/, imprimantes_scanners/  → Scrapers spécialisés
logs/                 → Journaux d'exécution
```

## ⚙️ Installation
```powershell
git clone https://github.com/wassim100/product-scraper.git
cd product-scraper
python -m venv venv
venv\Scripts\Activate
pip install -r requirements.txt
```

Créer un fichier `.env` (optionnel si valeurs par défaut) :
```env
GEMINI_API_KEY=VOTRE_CLE
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=scraping_db
```

## 🔑 Variables d'environnement principales
| Variable | Rôle |
|----------|------|
| HEADLESS_MODE | Exécution Chrome sans interface |
| FAST_SCRAPE | Active optimisations (timeouts courts, images désactivées) |
| MAX_PRODUCTS | Limite par run (0 = illimité) |
| ENABLE_DB | Active insertion DB |
| ENABLE_AI_CLEANING | Active nettoyage Gemini post-scrape (scheduler) |
| ENABLE_DEACTIVATE_MISSING | Désactive en base les produits non revus dans le run |
| SKIP_PDP_ENRICH | Saute l'enrichissement PDP (HP) pour accélérer |
| SCHEDULER_CATEGORIES | Filtre (serveurs,stockage,imprimantes_scanners) |
| SCHEDULER_SCRIPTS | Liste précise de scripts à exécuter |
| GEMINI_API_KEY | Clé API Gemini |

## 🧪 Exécution rapide (exemples)
Scraper 5 serveurs HP en mode rapide :
```powershell
$env:MAX_PRODUCTS=5; $env:FAST_SCRAPE="1"; $env:HEADLESS_MODE="1"; python .\serveurs\hp.py
```

Nettoyage IA manuel :
```powershell
python .\ai_processing\gemini_cleaning.py --in .\hp_servers_full.json --out .\hp_servers_full.cleaned.json --batch-size 2
```

Insertion DB (upsert) :
```powershell
$env:ENABLE_DEACTIVATE_MISSING="false"; python -c "from database.mysql_connector import save_to_database; print(save_to_database('hp_servers_full.cleaned.json','serveurs','HP'))"
```

Scheduler (catégorie imprimantes & scanners uniquement) :
```powershell
$env:SCHEDULER_CATEGORIES="imprimantes_scanners"; python -m automation.scheduler
```

## 🛢️ Schéma & DB
- Clés uniques : `(brand, sku)` et `(brand, link_hash)`
- Champs lifecycle: `is_active`, `scraped_at`, `last_seen`, `ai_processed` / `ai_processed_at`
- Désactivation conditionnelle contrôlée par `ENABLE_DEACTIVATE_MISSING`

## 🤖 IA (Gemini)
Flux : JSON brut → nettoyage (fusion specs / suppression bruit / normalisation clés) → `.cleaned.json` → DB.
Gestion : lots (`--batch-size`), limite (`--limit`), robustesse (retry basique).

## 🧹 Qualité / Robustesse
- Extraction HP refactorisée (tuiles → hints consolidés → JSON-LD → fallback PDP ciblé)
- `try/finally` systématique pour fermeture navigateur
- Image-blocking en mode `FAST_SCRAPE`
- Normalisation specs (regex CPU / cores / RAM / stockage / PSU)

## 🔍 CLI Base de Données
Exemples :
```powershell
python -m database.db_cli test
python -m database.db_cli list --table serveurs --brand HP --limit 5
python -m database.db_cli brands --table serveurs
python -m database.db_cli export --table serveurs --brand HP --out hp_export.json
```

## 📁 Fichiers ignorés (sécurité & propreté)
Le `.gitignore` exclut : logs, drivers, artefacts volumineux (`*_full.json`, fichiers `.cleaned.json`), environnements virtuels, secrets `.env`.

## 📝 Licence
MIT – voir `LICENSE`.

## ✅ Résumé des atouts
> Pipeline complet scrape → enrichissement conditionnel → nettoyage IA → upsert MySQL, modulaire, performant et traçable.

## ⭐ Contribution
PRs bienvenues : créez une branche, développez, testez, ouvrez une Pull Request.

---
Si ce projet vous est utile, une étoile GitHub est appréciée.

---

_Documentation finale consolidée – version stable._
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
