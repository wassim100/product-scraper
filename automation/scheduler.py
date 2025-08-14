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
logger = logging.getLogger(__name__)

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

                try:
                    process.wait(timeout=3600)  # Timeout de 1h
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

            # Post-traitement Gemini si activé
            cleaned_json_path = None
            if os.getenv('ENABLE_AI_CLEANING', 'false').lower() == 'true' and raw_json_path and os.path.exists(raw_json_path):
                cleaned_json_path = raw_json_path.replace('.json', '.cleaned.json')
                try:
                    logger.info(f"🧹 Gemini: {raw_json_path} → {cleaned_json_path}")
                    subprocess.check_call([
                        python_exec,
                        os.path.join('ai_processing', 'gemini_cleaning.py'),
                        '--in', raw_json_path,
                        '--out', cleaned_json_path
                    ])
                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ Échec post-traitement Gemini: {e}")
                    cleaned_json_path = None

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

        for category in categories:
            try:
                category_results = self.run_category(category)
                self.results['categories'][category] = category_results
                
                # Pause entre les catégories
                time.sleep(30)
                
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
