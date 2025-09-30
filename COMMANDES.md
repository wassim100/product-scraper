# Guide de commandes (démo / réunion)

Ce document regroupe des commandes PowerShell prêtes à copier-coller pour:
- Scraper 5 produits (ex: HP serveurs)
- Nettoyer/normaliser via Gemini (IA)
- Upserter en base MySQL
- Adapter rapidement aux autres catégories (stockage, imprimantes/scanners)

Toutes les commandes sont compatibles PowerShell Windows (utilisent `;` pour chaîner).

## Pré-requis
- Fichier `.env` contenant votre clé: `GEMINI_API_KEY=...`
- MySQL démarré et accessible (XAMPP/WAMP/service Windows)
- Test rapide MySQL (optionnel):
```powershell
python .\database\test_mysql.py
```

## Démo: Serveurs HP (5 produits)
1) Scraper (limite 5, rapide, headless)
```powershell
$env:MAX_PRODUCTS=5; $env:FAST_SCRAPE="1"; $env:HEADLESS_MODE="1"; python .\serveurs\hp.py
```

2) Nettoyage IA (Gemini) → produit un fichier nettoyé
```powershell
python .\ai_processing\gemini_cleaning.py --in .\hp_servers_full.json --out .\hp_servers_full.cleaned.json --batch-size 2
```
- Option: limiter le traitement IA pour la démo
```powershell
python .\ai_processing\gemini_cleaning.py --in .\hp_servers_full.json --out .\hp_servers_full.cleaned.json --limit 5 --batch-size 1
```

3) Upsert en base MySQL (sans désactiver les autres produits)
```powershell
$env:ENABLE_DEACTIVATE_MISSING="false"; python -c "from database.mysql_connector import save_to_database; print(save_to_database('hp_servers_full.cleaned.json','serveurs','HP'))"
```

4) Vérification rapide en base (échantillon des 5 derniers HP)
```powershell
python -c "import json, mysql.connector; from database.config import DB_CONFIG; cn=mysql.connector.connect(**DB_CONFIG); cur=cn.cursor(dictionary=True); cur.execute(\"SELECT brand,name,sku,link FROM serveurs WHERE brand=%s ORDER BY id DESC LIMIT 5\", (\"HP\",)); rows=cur.fetchall(); print(json.dumps(rows, indent=2, ensure_ascii=False)); cur.close(); cn.close()"
```

Notes:
- Le scraper HP ouvre la page produit au besoin pour compléter `name`/`tech_specs`.
- Après validation, pour un run complet: retirez `MAX_PRODUCTS` et (optionnel) remettez la désactivation:
```powershell
Remove-Item Env:MAX_PRODUCTS; $env:ENABLE_DEACTIVATE_MISSING="true"
```

## Adapter pour Stockage (ex: Dell, Lenovo)
1) Scraper (Dell ou Lenovo) avec limite 5
```powershell
$env:MAX_PRODUCTS=5; $env:FAST_SCRAPE="1"; $env:HEADLESS_MODE="1"; python .\stockage\dell.py
# ou
$env:MAX_PRODUCTS=5; $env:FAST_SCRAPE="1"; $env:HEADLESS_MODE="1"; python .\stockage\lenovo.py
```

2) Nettoyage IA
```powershell
python .\ai_processing\gemini_cleaning.py --in .\dell_storage_full.json --out .\dell_storage_full.cleaned.json --batch-size 2
# ou
python .\ai_processing\gemini_cleaning.py --in .\lenovo_storage_full.json --out .\lenovo_storage_full.cleaned.json --batch-size 2
```

3) Upsert en base
```powershell
$env:ENABLE_DEACTIVATE_MISSING="false"; python -c "from database.mysql_connector import save_to_database; print(save_to_database('dell_storage_full.cleaned.json','stockage','Dell'))"
# ou
$env:ENABLE_DEACTIVATE_MISSING="false"; python -c "from database.mysql_connector import save_to_database; print(save_to_database('lenovo_storage_full.cleaned.json','stockage','Lenovo'))"
```

## Adapter pour Imprimantes/Scanners (ex: HP, Epson)
1) Scraper (limite 5)
```powershell
$env:MAX_PRODUCTS=5; $env:FAST_SCRAPE="1"; $env:HEADLESS_MODE="1"; python .\imprimantes_scanners\hp.py
# ou
$env:MAX_PRODUCTS=5; $env:FAST_SCRAPE="1"; $env:HEADLESS_MODE="1"; python .\imprimantes_scanners\EpsonPrinters.py
```

2) Nettoyage IA
```powershell
python .\ai_processing\gemini_cleaning.py --in .\hp_printers_scanners_schema.json --out .\hp_printers_scanners_schema.cleaned.json --limit 5 --batch-size 1
# adaptez les chemins d'entrée/sortie selon le fichier produit par le scraper
```

3) Upsert en base
```powershell
$env:ENABLE_DEACTIVATE_MISSING="false"; python -c "from database.mysql_connector import save_to_database; print(save_to_database('hp_printers_scanners_schema.cleaned.json','imprimantes_scanners','HP'))"
# adaptez le brand/fichier si Epson
```

## Conseils / Dépannage rapide
- Clé IA manquante: ajoutez un `.env` à la racine avec `GEMINI_API_KEY=...`
- Chrome sans fenêtre (démo): gardez `HEADLESS_MODE=1`; pour voir le navigateur: `Remove-Item Env:HEADLESS_MODE`
- Erreurs MySQL: exécutez
```powershell
python .\database\test_mysql.py
```
- Accélérer la démo: gardez `FAST_SCRAPE=1`, utilisez `--limit` côté IA.

## Résumé des fichiers d’E/S fréquents
- Serveurs HP: `hp_servers_full.json` → `hp_servers_full.cleaned.json`
- Stockage Dell: `dell_storage_full.json` → `dell_storage_full.cleaned.json`
- Stockage Lenovo: `lenovo_storage_full.json` → `lenovo_storage_full.cleaned.json`
- Impr./Scanners HP: `hp_printers_scanners_schema.json` → `hp_printers_scanners_schema.cleaned.json`


## Parcourir la base (db_cli)
Quelques commandes pour lister/compter/exporter directement depuis MySQL.

1) Tester la connexion
```powershell
python -m database.db_cli test
```

2) Lister les dernières lignes d’une table (ex: 5 derniers HP serveurs)
```powershell
python -m database.db_cli list --table serveurs --brand HP --limit 5
```

3) Voir le volume par marque (ex: serveurs)
```powershell
python -m database.db_cli brands --table serveurs
```

4) Exporter vers JSON (ex: tous les HP serveurs)
```powershell
python -m database.db_cli export --table serveurs --brand HP --out hp_serveurs_export.json
```

Note: l'exécution directe (`python .\database\db_cli.py ...`) fonctionne aussi; le script ajuste le PYTHONPATH.


