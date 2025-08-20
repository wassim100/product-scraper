# Guide technique personnel

Ce document explique comment le projet fonctionne de bout en bout et décrit, fichier par fichier, ce qui a été fait techniquement.

## Vue d’ensemble

- Objectif: scraper des produits (serveurs, stockage, imprimantes/scanners) avec Selenium, normaliser les specs via Gemini (optionnel) et persister en MySQL.
- Orchestration: un scheduler central lance les scrapers par catégories, capture les logs, détecte les fichiers JSON, lance le nettoyage IA, puis insère en base avec des règles robustes d’upsert et de désactivation scope-marque.
- Sécurité test: variables d’environnement pour exécuter en headless, limiter le nombre de produits, activer/désactiver l’IA et la DB, et contrôler la désactivation des produits non vus.

## Flux d’exécution (pipeline)

1) Le scheduler lance un script (avec RUNNING_UNDER_SCHEDULER=1) et stream ses logs dans `logs/<script>_<timestamp>.log`.
2) Le script de scraping produit un JSON (ex. `epson_scanners_full.json`) et l’imprime dans la sortie (ligne « Données sauvées en JSON: … »), ce qui permet au scheduler de le détecter.
3) Si `ENABLE_AI_CLEANING=true`: le scheduler exécute `ai_processing/gemini_cleaning.py` pour produire un `.cleaned.json`.
4) Si `ENABLE_DB=true`: le scheduler lit le JSON (clean s’il existe, sinon raw), infère la marque (si homogène) et appelle `database/mysql_connector.save_to_database(...)` avec table et brand.
5) Si `ENABLE_DEACTIVATE_MISSING=true` et une `brand` est fournie: désactive en base les produits de cette marque non vus dans le lot courant (par SKU ou link_hash), et réactive les vus.

## Variables d’environnement clés

- HEADLESS_MODE=true|false: navigateur headless pour Selenium.
- ENABLE_DB=true|false: active l’insertion DB.
- ENABLE_AI_CLEANING=true|false: active le nettoyage Gemini.
- ENABLE_DEACTIVATE_MISSING=true|false: désactive les produits non vus (scope marque) après un insert.
- MAX_PRODUCTS: limite côté scripts Epson; dans le scheduler, un warning est loggé si MAX_PRODUCTS>0 et désactivation active.
- SCHEDULER_CATEGORIES: filtre des catégories (serveurs, stockage, imprimantes_scanners).
- SCHEDULER_SCRIPTS: filtre des scripts à l’intérieur d’une catégorie (noms chemins exacts).
- GEMINI_API_KEY: clé API Gemini.
- Paramètres MySQL via `database/config.py` (DB_CONFIG/DB_CONFIG_NO_DB) ou par défaut dans le code.

## Modèle de données et logique DB

- Tables: `serveurs`, `stockage`, `imprimantes_scanners` avec colonnes: brand, link, name, sku (nullable), link_hash (SHA-256 du link), tech_specs (JSON), timestamps, flags IA, is_active.
- Index uniques: (brand, sku) et (brand, link_hash) pour dédupliquer quand le SKU manque.
- Upsert: ON DUPLICATE KEY UPDATE met à jour les champs et `last_seen`, réactive `is_active=1`.
- Désactivation: par marque uniquement (sécurisé). Réactive d’abord les vus puis met `is_active=0` pour les non vus.

## Détails par fichier

- `automation/scheduler.py`
  - Registre des scripts par catégorie. Exécute chaque script comme sous-processus avec RUNNING_UNDER_SCHEDULER=1.
  - Capture la sortie vers `logs/` et détecte le chemin du JSON produit.
  - Si IA activée, appelle `ai_processing/gemini_cleaning.py` pour générer `.cleaned.json`.
  - Insertion DB: choisit la table en fonction du chemin (`serveurs`, `stockage`, `imprimantes_scanners`), infère la marque dans le JSON, applique la désactivation scope marque si activée.
  - Modes: exécution manuelle ou planification hebdomadaire (dimanche 02:00) via `schedule`.

- `database/mysql_connector.py`
  - Connexion MySQL, création base/tables et migrations légères (ajout colonnes, index uniques).
  - `insert_products`: upsert robuste via (brand, sku) et fallback (brand, link_hash).
  - `deactivate_missing`: réactivation des vus et désactivation des non vus par marque, pilotée par `ENABLE_DEACTIVATE_MISSING` via `save_to_database`.
  - `save_to_database(path, table, brand_filter)`: lit le JSON, filtre par brand si fourni, insère et gère la désactivation.

- `ai_processing/gemini_cleaning.py`
  - `GeminiProcessor`: nettoie/structure `tech_specs` (string ou dict) en JSON cohérent. Batching, retries, `response_mime_type=application/json`.
  - CLI: `--in` (entrée), `--out` (sortie). Utilise `GEMINI_API_KEY` (dotenv chargé).

- `main.py`
  - Modes:
    - setup: vérifie dépendances, chromedriver, et prépare la base.
    - scrape: lance un scraper spécifique via `--brand` et `--category`.
    - schedule: démarre le scheduler (ou run manuel avec `--manual-run`).
    - ai-process: traite un JSON par l’IA.

- Scrapers imprimantes/scanners
  - `imprimantes_scanners/EpsonPrinters.py`: imprimeurs Epson; sort `epson_printers_scanners_full.json`. Sous scheduler, pas d’insertion DB directe.
  - `imprimantes_scanners/EpsonScanner.py`: scanners Epson multi-catégories; sort `epson_scanners_full.json`. Dédup par SKU/URL; même pattern que printers.
  - `imprimantes_scanners/hp.py`: page HP mixte (imprimantes+scanners). Classification (PRINTER/SCANNER/MFP/ACCESSORY) + filtrage accessoires. Sort `hp_printers_scanners_schema.json`.

- Scrapers serveurs
  - `serveurs/asus.py`: pagination limitée (config de test), anti-détection, `asus_servers_full.json`.
  - `serveurs/dell.py`: navigation par onglets/sockets, extraction des cellules de tableau, `dell_servers_full.json`.
  - `serveurs/hp.py`: catégories HP (tower/micro/rack), données via JSON-LD + liens HTML, `hp_servers_full.json`.
  - `serveurs/lenovo.py`: multi-catégories Lenovo, combinaison specs liste + page détail, `lenovo_servers_full.json`.

- Scrapers stockage
  - `stockage/dell.py`: ObjectScale, Unity XT, PowerStore, PowerMax + PowerVault/PowerScale (onglets). Tab-click robustifié, `dell_storage_full.json`.
  - `stockage/lenovo.py`: plusieurs familles stockage Lenovo, click “Learn More” pour specs, `lenovo_storage_full.json`.

- Autres
  - `README.md`: guide public concis (scheduler, flags, exécution).
  - `.gitignore`: cache Python, venv, logs, drivers, JSON de sortie, secrets.
  - `requirements.txt`: selenium, mysql-connector-python, google-generativeai, schedule, python-dotenv, etc.

## Logs et artefacts

- Logs scheduler: `logs/scheduler.log` + un log par script exécuté.
- Artefacts JSON: fichiers `*_servers_full.json`, `*_storage_full.json`, `hp_printers_scanners_schema.json`, et variantes `.cleaned.json`.

## Bonnes pratiques et garde-fous

- Tests partiels: si vous mettez une limite (MAX_PRODUCTS, HP_MAX_PRODUCTS), désactivez la désactivation (`ENABLE_DEACTIVATE_MISSING=false`) pour ne pas dépublier par erreur.
- Sous scheduler, les scrapers ne doivent pas insérer dans la DB; ils respectent `RUNNING_UNDER_SCHEDULER` pour éviter les doublons.
- Index `(brand, sku)` + `(brand, link_hash)` couvrent les cas sans SKU.

## Ajouter un nouveau scraper (résumé)

1) Créez `categorie/vendeur.py` qui produit un JSON avec le schéma commun: brand, link, name, tech_specs (string ou dict), scraped_at, datasheet_link, sku? image_url? reviews?
2) Dans `automation/scheduler.py`, ajoutez le chemin du script à la catégorie.
3) Faites imprimer par le script une ligne « Données sauvées en JSON: <chemin> » après écriture.
4) Testez d’abord avec `ENABLE_DB=false` et des limites de produits.
5) Activez IA/DB et laissez le scheduler gérer cleaning+insertion.

## Points d’attention

- Chromedriver: présent à la racine, sinon Selenium Manager prend le relais.
- Cookies/popups: chaque scraper gère des sélecteurs de fallback.
- HP imprimantes/scanners: page mixte — classification intégrée et filtrage d’accessoires.
- Dell stockage: navigation par onglets nécessitant JS-click et attentes supplémentaires.
