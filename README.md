# 📦 Product Scraper - Server Specifications Extractor

Un système de scraping automatisé avancé pour extraire les spécifications techniques complètes des serveurs de différentes marques avec intelligence artificielle intégrée.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Selenium](https://img.shields.io/badge/Selenium-WebDriver-green.svg)](https://selenium.dev)
[![AI](https://img.shields.io/badge/AI-Gemini-orange.svg)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-red.svg)](LICENSE)

## 📋 Fonctionnalités

### 🎯 **Extraction Multi-Marques**
- **🔥 XFusion** : Scraper enhanced avec filtrage chassis/nodes et extraction détaillée
- **🖥️ Dell** : Serveurs AI PowerEdge avec navigation multi-onglets
- **🏢 HP** : Serveurs SMB avec couverture multi-URL
- **💻 Lenovo** : Scraping complet avec gestion des popups et scroll automation
- **⚡ ASUS** : Extraction avec pagination et spécifications détaillées

### 🔧 **Fonctionnalités Avancées**
- ✅ **Extraction des spécifications détaillées** depuis les pages individuelles
- ✅ **Filtrage intelligent** des chassis/nodes (XFusion)
- ✅ **Gestion des popups et cookies**
- ✅ **Scroll automation** pour le contenu dynamique
- ✅ **Multi-tab navigation** pour les ressources
- ✅ **Extraction des datasheets et images**
- ✅ **Pagination automatique**
- ✅ **Gestion d'erreurs robuste**

### 🤖 **Intelligence Artificielle**
- **Gemini AI Integration** : Nettoyage et structuration des données
- **Traitement automatique** des spécifications techniques
- **Optimisation de la qualité** des données extraites

## 🏗️ Structure du Projet

```
product-scraper/
│
├── 📁 serveurs/                    # Scrapers par marque
│   ├── xfusion.py                 # XFusion (Enhanced avec filtrage)
│   ├── dell.py                    # Dell PowerEdge AI Servers
│   ├── hp.py                      # HP SMB Servers
│   ├── lenovo.py                  # Lenovo avec automation avancée
│   └── asus.py                    # ASUS avec pagination
│
├── 📁 ai_processing/              # Traitement IA
│   └── gemini_cleaning.py         # Nettoyage Gemini AI
│
├── 📁 database/                   # Connexion base de données
│   └── mysql_connector.py         # Connecteur MySQL
│
├── 📁 automation/                 # Automatisation
│   └── scheduler.py               # Planificateur de tâches
│
├── 📁 stockage/                   # Scrapers stockage
│   ├── dell.py
│   └── lenovo.py
│
├── 📁 imprimantes_scanners/       # Scrapers imprimantes
│   ├── dell.py
│   └── hp.py
│
├── 📄 main.py                     # Script principal
├── 📄 requirements.txt            # Dépendances Python
├── 📄 README.md                   # Documentation
└── 📄 .gitignore                  # Fichiers à ignorer
```

## 🚀 Installation

### 1. **Cloner le repository**
```bash
git clone https://github.com/wassim100/product-scraper.git
cd product-scraper
```

### 2. **Créer un environnement virtuel**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows
```

### 3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

### 4. **Télécharger ChromeDriver**
- Télécharger [ChromeDriver](https://chromedriver.chromium.org/)
- Placer `chromedriver.exe` dans le répertoire racine

## 🎮 Utilisation

### **Scraping Individual par Marque**

```python
# XFusion Enhanced (avec filtrage chassis/nodes)
from serveurs.xfusion import XFusionServerScraperImproved

scraper = XFusionServerScraperImproved()
servers = scraper.scrape_all_categories()
scraper.save_to_json(servers, "xfusion_servers.json")
```

```python
# Dell AI Servers
python serveurs/dell.py
```

```python
# HP SMB Servers
python serveurs/hp.py
```

### **Script Principal (All-in-One)**
```bash
python main.py --brand all
```

### **Traitement IA avec Gemini**
```python
from ai_processing.gemini_cleaning import process_json_file

# Nettoyer et structurer les données
process_json_file("servers_raw.json", "servers_cleaned.json")
```

## 📊 Données Extraites

### **Format JSON Standard**
```json
{
  "brand": "XFusion",
  "category": "AI Servers",
  "name": "FusionServer G5500 V7",
  "link": "https://www.xfusion.com/...",
  "tech_specs": {
    "Form Factor": "4U AI server",
    "Processor": "2 x 4th/5th Gen Intel® Xeon® Scalable",
    "Memory": "32 x DIMMs at up to 5600 MT/s",
    "GPU Card": "10 x dual-width GPU cards",
    "Network": "3 x OCP 3.0 NICs",
    "...": "..."
  },
  "scraped_at": "2025-07-22T10:43:36.808174",
  "datasheet_link": "https://www.xfusion.com/en/resource/...",
  "image_url": "https://www.xfusion.com/wp-content/uploads/..."
}
```

## 🔧 Configuration

### **Variables d'environnement (.env)**
```bash
# API Keys
GEMINI_API_KEY=your_gemini_api_key_here

# Database (optionnel)
MYSQL_HOST=localhost
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=servers_db

# Scraping Settings
DELAY_BETWEEN_REQUESTS=2
MAX_RETRIES=3
HEADLESS_MODE=true
```

## 🎯 Fonctionnalités Spéciales

### **XFusion Enhanced**
- **Filtrage automatique** des chassis et nodes
- **Extraction détaillée** depuis les pages individuelles
- **Multi-tab navigation** pour datasheets et images
- **5 catégories** : Rack, High-Density, AI, Rack-Scale, FusionPoD

### **Lenovo Advanced**
- **Popup handling** automatique
- **Infinite scroll** automation
- **Load More** button clicking
- **Detailed specs** extraction from product pages

### **Dell Multi-Tab**
- **Socket-based** navigation
- **AI Servers** specialization
- **Tab switching** automation

## 🧪 Tests

### **Scripts de Test Disponibles**
```bash
# Test des spécifications détaillées XFusion
python test_detailed_specs.py

# Test du filtrage chassis/nodes
python test_filtered_scraper.py

# Test d'extraction de produit unique
python test_single_product.py
```

## 📈 Statistiques du Projet

- **5 marques** couvertes
- **245+ KB** de données serveurs
- **100%** spécifications détaillées (XFusion)
- **Filtrage intelligent** chassis/nodes
- **Multi-format** support (tableaux, cartes, listes)

## 🛠️ Technologies Utilisées

- **Python 3.8+**
- **Selenium WebDriver** : Automation web
- **Google Gemini AI** : Traitement intelligent des données
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
