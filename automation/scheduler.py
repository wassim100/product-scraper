import schedule
import time
import subprocess
import logging
import os
import sys
from datetime import datetime
import json
import threading
import re

# Configuration de logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/scheduler.log'),
        logging.StreamHandler()
    ]
)
# NOTE: On Windows consoles (cp1252), emojis/UTF-8 can raise UnicodeEncodeError.
# We'll reconfigure the root logger to use a safe console handler and UTF-8 file handler.
logger = logging.getLogger()  # root logger

# Remplacer le StreamHandler standard par un handler sûr pour la console Windows (évite UnicodeEncodeError)
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            enc = getattr(stream, 'encoding', None) or 'utf-8'
            # Supprimer/remplacer les caractères non encodables dans la console courante
            safe = msg.encode(enc, errors='ignore').decode(enc, errors='ignore')
            stream.write(safe + self.terminator)
            self.flush()
        except Exception:
            # Ne pas interrompre l'exécution pour un problème d'affichage console
            pass

# Appliquer une configuration sûre: retirer les handlers actuels et ajouter un FileHandler UTF-8 + SafeStreamHandler
_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
for h in list(logger.handlers):
    try:
        logger.removeHandler(h)
    except Exception:
        pass

file_handler = logging.FileHandler(f'{log_dir}/scheduler.log', encoding='utf-8')
file_handler.setFormatter(_fmt)
logger.addHandler(file_handler)

# Option pour couper les logs console si l'encodage Windows pose problème
if os.getenv('SCHEDULER_SILENT_CONSOLE', '1').strip().lower() not in {'1','true','yes','on'}:
    safe_console = SafeStreamHandler()
    safe_console.setFormatter(_fmt)
    logger.addHandler(safe_console)
logger.setLevel(logging.INFO)

class ScrapingScheduler:
    def __init__(self):
        self.scripts = {
            'serveurs': [
                'serveurs/asus.py',
                'serveurs/dell.py',
                'serveurs/hp.py',
                'serveurs/lenovo.py',
                'serveurs/xfusion.py'
            ],
            'stockage': [
                'stockage/dell.py',
                'stockage/lenovo.py'
            ],
            'imprimantes_scanners': [
                'imprimantes_scanners/EpsonPrinters.py',
                'imprimantes_scanners/EpsonScanner.py',
                'imprimantes_scanners/hp.py'
            ]
        }
        self.results = {}
        # Délai recommandé par script (secondes)
        self.script_timeouts = {
            'serveurs/lenovo.py': 1800,
            'stockage/dell.py': 1800,
            'stockage/lenovo.py': 1800,
            'imprimantes_scanners/hp.py': 1800,
            'imprimantes_scanners/EpsonScanner.py': 1800,
        }
    
    def run_script(self, script_path):
        """Exécute un script de scraping"""
        try:
            logger.info(f"🚀 Démarrage de {script_path}")
            start_time = datetime.now()
            
            # Exécuter le script
            env = os.environ.copy()
            # Forcer l'UTF-8 pour éviter les erreurs d'encodage (emojis, accents)
            env.setdefault('PYTHONIOENCODING', 'utf-8')
            env.setdefault('PYTHONUTF8', '1')

            # Utiliser le même interpréteur Python que le processus courant (venv)
            python_exec = sys.executable or 'python'

            # Préparer un fichier de log par script pour le streaming temps réel
            timestamp_run = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = script_path.replace('/', '_').replace('\\', '_').replace('.py', '')
            script_log_file = os.path.join(log_dir, f"{safe_name}_{timestamp_run}.log")
            logger.info(f"📝 Sortie temps réel → {script_log_file}")

            captured_lines: list[str] = []

            with open(script_log_file, 'w', encoding='utf-8') as logf:
                # Indiquer explicitement aux sous-processus qu'ils sont lancés par le scheduler
                env["RUNNING_UNDER_SCHEDULER"] = "1"
                # Valeurs par défaut pour plus de stabilité/rapidité
                env.setdefault("HEADLESS_MODE", "1")
                env.setdefault("FAST_SCRAPE", "1")
                env.setdefault("MAX_PRODUCTS", "20")
                # Aligner l'environnement spécifique HP imprimantes sur la limite globale
                if script_path == 'imprimantes_scanners/hp.py':
                    env.setdefault('HP_MAX_PRODUCTS', env.get('MAX_PRODUCTS', '20'))
                process = subprocess.Popen(
                    [python_exec, script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=env
                )

                def stream_output(pipe):
                    try:
                        for line in iter(pipe.readline, ''):
                            logf.write(line)
                            logf.flush()
                            captured_lines.append(line)
                    finally:
                        try:
                            pipe.close()
                        except Exception:
                            pass

                t = threading.Thread(target=stream_output, args=(process.stdout,))
                t.daemon = True
                t.start()

                # Timeout configurable par env (override possible par script)
                default_timeout = self.script_timeouts.get(script_path, 900)
                env_timeout = int(os.getenv('SCHEDULER_SCRIPT_TIMEOUT_SECONDS', str(default_timeout)))
                # Choisir le plus grand pour éviter d'écraser les délais spécifiques
                base_timeout = max(default_timeout, env_timeout)
                # Échelle dynamique selon MAX_PRODUCTS (ex: 20 → x4), avec plafond configurable
                try:
                    mp_val = int(env.get('MAX_PRODUCTS', '5'))
                except Exception:
                    mp_val = 5
                scale = max(1, mp_val // 5)  # 5→x1, 10→x2, 15→x3, 20→x4
                max_cap_env = os.getenv('SCHEDULER_MAX_TIMEOUT_CAP_SECONDS', '21600')  # défaut 6h
                try:
                    max_cap = int(max_cap_env)
                except Exception:
                    max_cap = 21600
                computed = int(base_timeout * scale)
                timeout_s = computed if max_cap <= 0 else int(min(max_cap, computed))
                try:
                    process.wait(timeout=timeout_s)
                except subprocess.TimeoutExpired:
                    process.kill()
                    t.join(timeout=5)
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    logger.error(f"⏰ {script_path} a dépassé le timeout")
                    return {
                        'status': 'timeout',
                        'duration': duration,
                        'error': 'Timeout expired',
                        'log_file': script_log_file
                    }

                # S'assurer que le thread a fini d'écrire
                t.join()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            output_text = ''.join(captured_lines)

            # Essayer de détecter le chemin du JSON dans les sorties
            raw_json_path = None
            # Plusieurs scripts impriment ce motif
            m = re.search(r"Données sauvées en JSON:\s*(.+)", output_text)
            if not m:
                # Certains scripts impriment le nom de fichier simple sans chemin
                m2 = re.search(r"(\w+_servers_full\.json|\w+_storage_full\.json|hp_printers_scanners_schema\.json|epson_\w+\.json)", output_text)
                if m2:
                    raw_json_path = os.path.join(os.path.dirname(__file__), "..", m2.group(1))
            else:
                raw_json_path = m.group(1).strip()

            # Post-traitement Gemini si activé (avec possibilité de le désactiver par catégorie)
            cleaned_json_path = None
            enable_ai_cleaning = os.getenv('ENABLE_AI_CLEANING', 'false').lower() == 'true'
            # Catégorie et marque déduites du chemin du script
            category_name = 'imprimantes_scanners'
            if 'serveurs' in script_path:
                category_name = 'serveurs'
            elif 'stockage' in script_path:
                category_name = 'stockage'
            # Marque = nom du fichier sans extension (ex: serveurs/dell.py -> dell)
            brand_name = os.path.splitext(os.path.basename(script_path))[0].lower()

            # Liste CSV des catégories à exclure du nettoyage IA (ex: "serveurs,stockage")
            skip_cat_csv = os.getenv('AI_CLEANING_SKIP_CATEGORIES', '').strip()
            skip_cat_set = {c.strip().lower() for c in skip_cat_csv.split(',') if c.strip()}
            # Liste CSV des marques à exclure globalement (ex: "dell,asus")
            skip_brand_csv = os.getenv('AI_CLEANING_SKIP_BRANDS', '').strip()
            skip_brand_set = {b.strip().lower() for b in skip_brand_csv.split(',') if b.strip()}
            # Règles ciblées "categorie:marque" (ex: "serveurs:dell,stockage:lenovo")
            skip_rules_csv = os.getenv('AI_CLEANING_SKIP_RULES', '').strip()
            skip_rules_set = set()
            if skip_rules_csv:
                for token in skip_rules_csv.split(','):
                    token = token.strip().lower()
                    if not token:
                        continue
                    if ':' in token:
                        cat, br = token.split(':', 1)
                        skip_rules_set.add((cat.strip(), br.strip()))
            is_rule_skipped = (category_name.lower(), brand_name) in skip_rules_set
            should_clean = (
                enable_ai_cleaning
                and (category_name.lower() not in skip_cat_set)
                and (brand_name not in skip_brand_set)
                and (not is_rule_skipped)
            )

            if should_clean and raw_json_path and os.path.exists(raw_json_path):
                cleaned_json_path = raw_json_path.replace('.json', '.cleaned.json')
                try:
                    logger.info(f"🧹 Gemini ({category_name}/{brand_name}): {raw_json_path} → {cleaned_json_path}")
                    batch_size = os.getenv('AI_BATCH_SIZE', '3')
                    cmd = [
                        python_exec,
                        os.path.join('ai_processing', 'gemini_cleaning.py'),
                        '--in', raw_json_path,
                        '--out', cleaned_json_path,
                        '--batch-size', batch_size
                    ]
                    subprocess.check_call(cmd)
                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Échec post-traitement Gemini: {e}")
                    cleaned_json_path = None

            # Suppression globale des descriptions dans les fichiers JSON de sortie
            def _strip_descriptions_inplace(path: str):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    def _strip(o):
                        if isinstance(o, dict):
                            return {k: _strip(v) for k, v in o.items() if k.lower() != 'description'}
                        if isinstance(o, list):
                            return [_strip(x) for x in o]
                        return o
                    new_data = _strip(data)
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(new_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"🧺 Descriptions supprimées → {path}")
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de supprimer 'description' dans {path}: {e}")

            drop_desc_global = os.getenv('DROP_DESCRIPTION_GLOBAL', 'true').strip().lower() in {'1','true','yes','on'}
            if drop_desc_global:
                for p in [cleaned_json_path, raw_json_path]:
                    if p and os.path.exists(p):
                        _strip_descriptions_inplace(p)

            # Normalisation: remonter SKU au niveau racine si présent dans tech_specs
            def _hoist_sku(path: str):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if not isinstance(data, list):
                        return
                    changed = False
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        ts = item.get('tech_specs') or {}
                        if isinstance(ts, dict):
                            sku_val = ts.pop('SKU', None) or ts.pop('sku', None)
                            if sku_val:
                                if not item.get('sku'):
                                    item['sku'] = sku_val
                                changed = True
                    if changed:
                        with open(path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        logger.info(f"📦 Normalisé: 'sku' hoisté vers la racine → {path}")
                except Exception as e:
                    logger.warning(f"⚠️ Normalisation SKU échouée pour {path}: {e}")

            for p in [cleaned_json_path, raw_json_path]:
                if p and os.path.exists(p):
                    _hoist_sku(p)

            # Validation légère du JSON et diagnostic
            def _validate_json_file(path: str, context: str):
                findings = []
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if not isinstance(data, list):
                        findings.append('root_not_list')
                        return findings
                    if len(data) == 0:
                        findings.append('empty_list')
                    # Règles génériques
                    spec_tokens = ['gb ram', 'tb', 'ssd', 'hdd', 'xeon', 'cores', 'core', 'silver', 'gold', 'bronze', 'w power']
                    for idx, item in enumerate(data[:50]):  # limiter pour les gros fichiers
                        if not isinstance(item, dict):
                            findings.append(f'item_{idx}_not_dict')
                            continue
                        # Clés requises
                        for key in ['brand', 'link', 'name', 'tech_specs']:
                            if key not in item:
                                findings.append(f'missing_{key}_at_{idx}')
                        # Sanity name
                        name = (item.get('name') or '').strip()
                        if not name:
                            findings.append(f'empty_name_{idx}')
                        # Si le nom contient trop de specs, signaler
                        name_low = name.lower()
                        if any(tok in name_low for tok in spec_tokens):
                            findings.append(f'name_may_contain_specs_{idx}')
                        # tech_specs doit être un objet
                        ts = item.get('tech_specs')
                        if ts is None:
                            findings.append(f'no_tech_specs_{idx}')
                        elif not isinstance(ts, dict):
                            findings.append(f'tech_specs_not_object_{idx}')
                        # lien plausible
                        link = item.get('link')
                        if not (isinstance(link, str) and link.startswith('http')):
                            findings.append(f'bad_link_{idx}')
                    return findings
                except Exception as e:
                    return [f'exception:{e}']

            validation_findings = []
            json_for_validation = cleaned_json_path or raw_json_path
            if json_for_validation and os.path.exists(json_for_validation):
                validation_findings = _validate_json_file(json_for_validation, f'{category_name}/{brand_name}')
                if validation_findings:
                    logger.warning(f"🔎 Validation {category_name}/{brand_name}: {len(validation_findings)} avertissements")
                    for fnd in validation_findings[:20]:
                        logger.warning(f"   • {fnd}")

            # Insertion en base avec le JSON nettoyé si demandé
            if os.getenv('ENABLE_DB', 'false').lower() == 'true':
                target_json = cleaned_json_path or raw_json_path
                if target_json and os.path.exists(target_json):
                    # Choisir la table selon le chemin du script
                    table = 'imprimantes_scanners'
                    if 'serveurs' in script_path:
                        table = 'serveurs'
                    elif 'stockage' in script_path:
                        table = 'stockage'
                    # Alerte si run réduit et désactivation active
                    max_products = os.getenv('MAX_PRODUCTS')
                    enable_deact = os.getenv('ENABLE_DEACTIVATE_MISSING', 'true').lower() == 'true'
                    if max_products and max_products.isdigit() and int(max_products) > 0 and enable_deact:
                        logger.warning("⚠️ MAX_PRODUCTS>0 et ENABLE_DEACTIVATE_MISSING=true: cela peut désactiver des produits non traités lors d'un run de test.")
                    try:
                        logger.info(f"💾 Insertion DB depuis {target_json} dans '{table}' (avec détection de la marque)")
                        code = (
                            "import json\n"
                            "from database.mysql_connector import save_to_database\n"
                            f"p=r'''{target_json}'''\n"
                            "brand=None\n"
                            "try:\n"
                            "    with open(p,'r',encoding='utf-8') as f:\n"
                            "        data=json.load(f)\n"
                            "    brands=set((item.get('brand') or '').strip() for item in data if item.get('brand'))\n"
                            "    brand=list(brands)[0] if len(brands)==1 else None\n"
                            "except Exception:\n"
                            "    brand=None\n"
                            f"print(save_to_database(r'''{target_json}''', r'''{table}''', brand))\n"
                        )
                        subprocess.check_call([python_exec, '-c', code])
                    except subprocess.CalledProcessError as e:
                        logger.error(f"❌ Insertion DB échouée: {e}")

            if process.returncode == 0:
                logger.info(f"✅ {script_path} terminé avec succès en {duration:.0f}s")
                return {
                    'status': 'success',
                    'duration': duration,
                    'output': output_text,
                    'log_file': script_log_file,
                    'raw_json': raw_json_path,
                    'cleaned_json': cleaned_json_path
                }
            else:
                logger.error(f"❌ {script_path} a échoué (code {process.returncode}). Voir {script_log_file}")
                return {
                    'status': 'error',
                    'duration': duration,
                    'error': f'Exit code {process.returncode}',
                    'log_file': script_log_file,
                    'raw_json': raw_json_path,
                    'cleaned_json': cleaned_json_path
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f"⏰ {script_path} a dépassé le timeout")
            return {
                'status': 'timeout',
                'duration': 3600,
                'error': 'Timeout expired'
            }
        except Exception as e:
            logger.error(f"💥 Erreur lors de l'exécution de {script_path}: {e}")
            return {
                'status': 'exception',
                'duration': 0,
                'error': str(e)
            }
    
    def run_category(self, category):
        """Exécute tous les scripts d'une catégorie"""
        logger.info(f"📂 Démarrage de la catégorie: {category}")
        category_results = {}
        
        # Filtre optionnel de scripts (CSV) via env
        scripts_filter = os.getenv('SCHEDULER_SCRIPTS')
        scripts_to_run = self.scripts.get(category, [])
        if scripts_filter:
            wanted = {s.strip() for s in scripts_filter.split(',') if s.strip()}
            scripts_to_run = [s for s in scripts_to_run if s in wanted]

        for script in scripts_to_run:
            if os.path.exists(script):
                result = self.run_script(script)
                category_results[script] = result
            else:
                abs_path = os.path.abspath(script)
                logger.warning(f"⚠️ Script non trouvé: {script} (abs: {abs_path})")
                category_results[script] = {
                    'status': 'not_found',
                    'duration': 0,
                    'error': 'File not found'
                }
        
        return category_results
    
    def run_all_scrapers(self):
        """Exécute tous les scrapers"""
        logger.info("🎯 === DÉMARRAGE DU SCRAPING HEBDOMADAIRE ===")
        start_time = datetime.now()
        
        self.results = {
            'start_time': start_time.isoformat(),
            'categories': {}
        }
        
        # Exécuter chaque catégorie (filtrable via env SCHEDULER_CATEGORIES)
        categories_filter = os.getenv('SCHEDULER_CATEGORIES')
        categories = list(self.scripts.keys())
        if categories_filter:
            wanted = {c.strip() for c in categories_filter.split(',') if c.strip()}
            categories = [c for c in categories if c in wanted]
        pause_between = int(os.getenv('SCHEDULER_PAUSE_BETWEEN_CATEGORIES_SECONDS', '5'))
        for category in categories:
            try:
                category_results = self.run_category(category)
                self.results['categories'][category] = category_results
                # Pause entre les catégories
                time.sleep(pause_between)
            except Exception as e:
                logger.error(f"❌ Erreur dans la catégorie {category}: {e}")
                self.results['categories'][category] = {
                    'error': str(e)
                }
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        self.results['end_time'] = end_time.isoformat()
        self.results['total_duration'] = total_duration
        
        # Sauvegarder le rapport
        self.save_report()
        
        # Résumé
        self.print_summary()
        
        logger.info(f"🏁 Scraping hebdomadaire terminé en {total_duration/60:.1f} minutes")
    
    def save_report(self):
        """Sauvegarde le rapport d'exécution"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"{log_dir}/scraping_report_{timestamp}.json"
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            logger.info(f"📊 Rapport sauvegardé: {report_file}")
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde rapport: {e}")
    
    def print_summary(self):
        """Affiche un résumé des résultats"""
        total_scripts = 0
        successful_scripts = 0
        failed_scripts = 0
        
        logger.info("\n📈 === RÉSUMÉ DU SCRAPING ===")
        
        for category, scripts in self.results.get('categories', {}).items():
            logger.info(f"\n📂 {category.upper()}:")
            
            for script, result in scripts.items():
                total_scripts += 1
                status = result.get('status', 'unknown')
                duration = result.get('duration', 0)
                
                if status == 'success':
                    successful_scripts += 1
                    logger.info(f"  ✅ {script} - {duration:.0f}s")
                else:
                    failed_scripts += 1
                    error = result.get('error', 'Unknown error')
                    logger.info(f"  ❌ {script} - {status}: {error}")
        
        logger.info(f"\n🎯 TOTAL: {successful_scripts}/{total_scripts} succès")
        logger.info(f"⏱️ Durée totale: {self.results.get('total_duration', 0)/60:.1f} minutes")
    
    def schedule_weekly_run(self):
        """Programme l'exécution hebdomadaire"""
        # Programmer pour chaque dimanche à 2h du matin
        schedule.every().sunday.at("02:00").do(self.run_all_scrapers)
        
        logger.info("📅 Scraping programmé chaque dimanche à 2h00")
        logger.info("⏰ En attente du prochain déclenchement...")
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Vérifier chaque minute

def run_manual_scraping():
    """Exécution manuelle pour test"""
    scheduler = ScrapingScheduler()
    scheduler.run_all_scrapers()

def start_scheduler():
    """Démarrer le scheduler automatique"""
    scheduler = ScrapingScheduler()
    scheduler.schedule_weekly_run()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--manual":
        # Exécution manuelle
        run_manual_scraping()
    else:
        # Démarrer le scheduler
        start_scheduler()
