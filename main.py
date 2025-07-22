#!/usr/bin/env python3
"""
Script principal pour le système de scraping automatisé
Système de scrapping automatique pour l'extraction et la structuration des données produits
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime

# Configuration de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Vérifie que toutes les dépendances sont installées"""
    required_packages = [
        'selenium',
        'mysql.connector',
        'google.generativeai',
        'schedule'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'mysql.connector':
                import mysql.connector
            elif package == 'google.generativeai':
                import google.generativeai
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"❌ Packages manquants: {missing_packages}")
        logger.info("💡 Installez-les avec: pip install -r requirements.txt")
        return False
    
    logger.info("✅ Toutes les dépendances sont installées")
    return True

def check_chromedriver():
    """Vérifie la présence de ChromeDriver"""
    chromedriver_path = "chromedriver.exe"
    if not os.path.exists(chromedriver_path):
        logger.error(f"❌ ChromeDriver non trouvé: {chromedriver_path}")
        logger.info("💡 Téléchargez ChromeDriver depuis https://chromedriver.chromium.org/")
        return False
    
    logger.info("✅ ChromeDriver trouvé")
    return True

def setup_database():
    """Configure la base de données MySQL"""
    try:
        from database.mysql_connector import MySQLConnector
        
        db = MySQLConnector()
        db.create_database()
        if db.connect():
            db.create_tables()
            db.close()
            logger.info("✅ Base de données configurée")
            return True
        else:
            logger.error("❌ Impossible de se connecter à MySQL")
            return False
    except Exception as e:
        logger.error(f"❌ Erreur configuration base de données: {e}")
        return False

def run_scraper(script_path):
    """Exécute un scraper spécifique"""
    if not os.path.exists(script_path):
        logger.error(f"❌ Script non trouvé: {script_path}")
        return False
    
    try:
        logger.info(f"🚀 Exécution de {script_path}")
        
        # Importer et exécuter le module
        script_dir = os.path.dirname(script_path)
        script_name = os.path.basename(script_path).replace('.py', '')
        
        # Ajouter le répertoire au path
        sys.path.insert(0, script_dir)
        
        # Import dynamique
        module = __import__(script_name)
        
        logger.info(f"✅ {script_path} exécuté avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'exécution de {script_path}: {e}")
        return False

def run_ai_processing(input_file, output_file=None):
    """Lance le post-traitement IA"""
    if not os.path.exists(input_file):
        logger.error(f"❌ Fichier d'entrée non trouvé: {input_file}")
        return False
    
    if not output_file:
        name, ext = os.path.splitext(input_file)
        output_file = f"{name}_cleaned{ext}"
    
    try:
        from ai_processing.gemini_cleaning import process_json_file
        
        # Vérifier la clé API
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.warning("⚠️ GEMINI_API_KEY non définie, traitement IA ignoré")
            return False
        
        process_json_file(input_file, output_file, api_key)
        logger.info(f"✅ Traitement IA terminé: {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur traitement IA: {e}")
        return False

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(
        description="Système de scraping automatisé pour infrastructure IT"
    )
    
    parser.add_argument(
        '--mode', 
        choices=['setup', 'scrape', 'schedule', 'ai-process'],
        default='setup',
        help='Mode d\'exécution'
    )
    
    parser.add_argument(
        '--brand',
        choices=['asus', 'hp', 'dell', 'lenovo', 'xfusion'],
        help='Marque à scraper'
    )
    
    parser.add_argument(
        '--category',
        choices=['serveurs', 'stockage', 'imprimantes_scanners'],
        help='Catégorie de produits'
    )
    
    parser.add_argument(
        '--input-file',
        help='Fichier d\'entrée pour le traitement IA'
    )
    
    parser.add_argument(
        '--output-file',
        help='Fichier de sortie pour le traitement IA'
    )
    
    parser.add_argument(
        '--manual-run',
        action='store_true',
        help='Exécution manuelle du scraping complet'
    )
    
    args = parser.parse_args()
    
    logger.info("🎯 === SYSTÈME DE SCRAPING AUTOMATISÉ ===")
    logger.info(f"Mode: {args.mode}")
    
    # Mode setup - Configuration initiale
    if args.mode == 'setup':
        logger.info("🔧 Configuration du système...")
        
        if not check_dependencies():
            return 1
        
        if not check_chromedriver():
            return 1
        
        if not setup_database():
            return 1
        
        logger.info("✅ Configuration terminée avec succès!")
        logger.info("\n📖 Utilisation:")
        logger.info("  python main.py --mode scrape --brand asus --category serveurs")
        logger.info("  python main.py --mode schedule")
        logger.info("  python main.py --mode ai-process --input-file data.json")
        
        return 0
    
    # Mode scrape - Scraping spécifique
    elif args.mode == 'scrape':
        if not args.brand or not args.category:
            logger.error("❌ --brand et --category requis pour le scraping")
            return 1
        
        script_path = f"{args.category}/{args.brand}.py"
        return 0 if run_scraper(script_path) else 1
    
    # Mode schedule - Automatisation
    elif args.mode == 'schedule':
        try:
            if args.manual_run:
                from automation.scheduler import run_manual_scraping
                run_manual_scraping()
            else:
                from automation.scheduler import start_scheduler
                start_scheduler()
            return 0
        except Exception as e:
            logger.error(f"❌ Erreur scheduler: {e}")
            return 1
    
    # Mode ai-process - Traitement IA
    elif args.mode == 'ai-process':
        if not args.input_file:
            logger.error("❌ --input-file requis pour le traitement IA")
            return 1
        
        return 0 if run_ai_processing(args.input_file, args.output_file) else 1
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n🛑 Interruption par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {e}")
        sys.exit(1)
