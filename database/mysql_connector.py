import mysql.connector
from mysql.connector import Error
import json
import logging
from datetime import datetime
import os

# Importer la configuration
try:
    from database.config import DB_CONFIG, DB_CONFIG_NO_DB
except ImportError:
    # Configuration par défaut si le fichier config n'existe pas
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'scraping_db',
        'user': 'root',
        'password': '',
        'charset': 'utf8mb4',
        'autocommit': True
    }
    DB_CONFIG_NO_DB = {
        'host': 'localhost',
        'user': 'root',
        'password': '',
        'charset': 'utf8mb4'
    }

# Configuration de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MySQLConnector:
    def __init__(self, config=None):
        """
        Initialise la connexion MySQL avec configuration personnalisée
        """
        if config:
            self.config = config
        else:
            self.config = DB_CONFIG.copy()
        self.connection = None
        
    def test_mysql_availability(self):
        """Teste si MySQL est disponible et accessible"""
        try:
            # Test avec configuration sans base de données
            test_config = DB_CONFIG_NO_DB.copy()
            test_connection = mysql.connector.connect(**test_config)
            test_connection.close()
            logger.info("✅ MySQL est accessible")
            return True
        except Error as e:
            logger.error(f"❌ MySQL non accessible: {e}")
            logger.info("💡 Vérifiez que MySQL est installé et démarré")
            logger.info("💡 Pour XAMPP: Démarrez Apache et MySQL")
            logger.info("💡 Pour installation standalone: Vérifiez le service MySQL")
            return False
        
    def connect(self):
        """Établit la connexion à la base de données"""
        try:
            # D'abord tester si MySQL est disponible
            if not self.test_mysql_availability():
                return False
                
            # Créer la base de données si elle n'existe pas
            self.create_database()
            
            # Se connecter à la base de données
            self.connection = mysql.connector.connect(**self.config)
            if self.connection.is_connected():
                logger.info(f"✅ Connexion réussie à MySQL - Base: {self.config['database']}")
                return True
        except Error as e:
            logger.error(f"❌ Erreur de connexion MySQL: {e}")
            return False
    
    def create_database(self):
        """Crée la base de données si elle n'existe pas"""
        try:
            temp_config = DB_CONFIG_NO_DB.copy()
            temp_connection = mysql.connector.connect(**temp_config)
            cursor = temp_connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.config['database']}")
            cursor.close()
            temp_connection.close()
            logger.info(f"✅ Base de données '{self.config['database']}' créée/vérifiée")
        except Error as e:
            logger.error(f"❌ Erreur création base de données: {e}")
            raise
    
    def create_tables(self):
        """Crée les tables selon le schéma du cahier des charges"""
        if not self.connection or not self.connection.is_connected():
            self.connect()
        
        tables = {
            'serveurs': """
                CREATE TABLE IF NOT EXISTS serveurs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    brand VARCHAR(100) NOT NULL,
                    link TEXT NOT NULL,
                    name VARCHAR(500) NOT NULL,
                    tech_specs JSON,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    datasheet_link TEXT,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_product (brand, name)
                )
            """,
            'stockage': """
                CREATE TABLE IF NOT EXISTS stockage (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    brand VARCHAR(100) NOT NULL,
                    link TEXT NOT NULL,
                    name VARCHAR(500) NOT NULL,
                    tech_specs JSON,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    datasheet_link TEXT,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_product (brand, name)
                )
            """,
            'imprimantes_scanners': """
                CREATE TABLE IF NOT EXISTS imprimantes_scanners (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    brand VARCHAR(100) NOT NULL,
                    link TEXT NOT NULL,
                    name VARCHAR(500) NOT NULL,
                    tech_specs JSON,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    datasheet_link TEXT,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_product (brand, name)
                )
            """
        }
        
        try:
            cursor = self.connection.cursor()
            for table_name, query in tables.items():
                cursor.execute(query)
                logger.info(f"✅ Table '{table_name}' créée/vérifiée")
            
            self.connection.commit()
            cursor.close()
            
        except Error as e:
            logger.error(f"❌ Erreur création tables: {e}")
    
    def insert_products(self, products_data, table_name):
        """
        Insère les produits dans la table spécifiée
        """
        if not self.connection or not self.connection.is_connected():
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            
            # Requête d'insertion avec gestion des doublons
            query = f"""
                INSERT INTO {table_name} 
                (brand, link, name, tech_specs, scraped_at, datasheet_link, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                tech_specs = VALUES(tech_specs),
                scraped_at = VALUES(scraped_at),
                datasheet_link = VALUES(datasheet_link),
                image_url = VALUES(image_url),
                updated_at = CURRENT_TIMESTAMP
            """
            
            inserted_count = 0
            updated_count = 0
            
            for product in products_data:
                # Conversion des tech_specs en JSON string
                tech_specs_json = json.dumps(product.get('tech_specs', {}), ensure_ascii=False)
                
                values = (
                    product.get('brand', ''),
                    product.get('link', ''),
                    product.get('name', ''),
                    tech_specs_json,
                    product.get('scraped_at', datetime.now().isoformat()),
                    product.get('datasheet_link'),
                    product.get('image_url', '')
                )
                
                # Vérifier si le produit existe déjà
                check_query = f"SELECT id FROM {table_name} WHERE brand = %s AND name = %s"
                cursor.execute(check_query, (product.get('brand'), product.get('name')))
                exists = cursor.fetchone()
                
                cursor.execute(query, values)
                
                if exists:
                    updated_count += 1
                else:
                    inserted_count += 1
            
            self.connection.commit()
            cursor.close()
            
            logger.info(f"✅ {inserted_count} nouveaux produits insérés, {updated_count} mis à jour dans '{table_name}'")
            return inserted_count, updated_count
            
        except Error as e:
            logger.error(f"❌ Erreur insertion dans {table_name}: {e}")
            return 0, 0
    
    def get_products(self, table_name, brand=None):
        """Récupère les produits d'une table"""
        if not self.connection or not self.connection.is_connected():
            self.connect()
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            if brand:
                query = f"SELECT * FROM {table_name} WHERE brand = %s ORDER BY created_at DESC"
                cursor.execute(query, (brand,))
            else:
                query = f"SELECT * FROM {table_name} ORDER BY created_at DESC"
                cursor.execute(query)
            
            products = cursor.fetchall()
            cursor.close()
            
            # Convertir les tech_specs JSON en dict
            for product in products:
                if product.get('tech_specs'):
                    try:
                        product['tech_specs'] = json.loads(product['tech_specs'])
                    except:
                        product['tech_specs'] = {}
            
            return products
            
        except Error as e:
            logger.error(f"❌ Erreur récupération depuis {table_name}: {e}")
            return []
    
    def close(self):
        """Ferme la connexion"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("✅ Connexion MySQL fermée")

def save_to_database(json_file_path, table_name, brand_filter=None):
    """
    Fonction utilitaire pour sauvegarder un fichier JSON en base
    """
    try:
        # Initialiser le connecteur
        db = MySQLConnector()
        
        # Tester la disponibilité de MySQL
        if not db.test_mysql_availability():
            logger.error("❌ MySQL n'est pas disponible")
            return False
        
        # Se connecter à la base
        if not db.connect():
            logger.error("❌ Impossible de se connecter à MySQL")
            return False
        
        # Créer les tables
        db.create_tables()
        
        # Charger les données JSON
        with open(json_file_path, 'r', encoding='utf-8') as f:
            products_data = json.load(f)
        
        # Filtrer par marque si spécifié
        if brand_filter:
            products_data = [p for p in products_data if p.get('brand', '').lower() == brand_filter.lower()]
        
        # Sauvegarder en base
        inserted, updated = db.insert_products(products_data, table_name)
        
        logger.info(f"✅ Sauvegarde terminée: {inserted} insertions, {updated} mises à jour")
        db.close()
        return True
        
    except FileNotFoundError:
        logger.error(f"❌ Fichier JSON non trouvé: {json_file_path}")
        return False
    except json.JSONDecodeError:
        logger.error(f"❌ Fichier JSON invalide: {json_file_path}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur lors de la sauvegarde: {e}")
        return False
        
        logger.info(f"🎯 Sauvegarde terminée: {inserted} ajoutés, {updated} mis à jour")
        
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde: {e}")
    
    finally:
        db.close()

if __name__ == "__main__":
    # Test de connexion
    db = MySQLConnector()
    db.create_database()
    if db.connect():
        db.create_tables()
        db.close()