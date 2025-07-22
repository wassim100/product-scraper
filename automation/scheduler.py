import schedule
import time
import subprocess
import logging
import os
from datetime import datetime
import json

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
                'imprimantes_scanners/hp.py',
                'imprimantes_scanners/dell.py'
            ]
        }
        self.results = {}
    
    def run_script(self, script_path):
        """Exécute un script de scraping"""
        try:
            logger.info(f"🚀 Démarrage de {script_path}")
            start_time = datetime.now()
            
            # Exécuter le script
            result = subprocess.run(
                ['python', script_path],
                capture_output=True,
                text=True,
                timeout=3600  # Timeout de 1h
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if result.returncode == 0:
                logger.info(f"✅ {script_path} terminé avec succès en {duration:.0f}s")
                return {
                    'status': 'success',
                    'duration': duration,
                    'output': result.stdout
                }
            else:
                logger.error(f"❌ {script_path} a échoué: {result.stderr}")
                return {
                    'status': 'error',
                    'duration': duration,
                    'error': result.stderr
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
        
        for script in self.scripts.get(category, []):
            if os.path.exists(script):
                result = self.run_script(script)
                category_results[script] = result
            else:
                logger.warning(f"⚠️ Script non trouvé: {script}")
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
        
        # Exécuter chaque catégorie
        for category in self.scripts.keys():
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
