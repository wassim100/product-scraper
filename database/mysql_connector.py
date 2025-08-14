import mysql.connector
from mysql.connector import Error
import json
import logging
from datetime import datetime
import os
import hashlib

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
                    sku VARCHAR(100) NULL,
                    link_hash CHAR(64) NULL,
                    tech_specs JSON,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    datasheet_link TEXT,
                    image_url TEXT,
                    ai_processed TINYINT(1) DEFAULT 0,
                    ai_processed_at TIMESTAMP NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """,
            'stockage': """
                CREATE TABLE IF NOT EXISTS stockage (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    brand VARCHAR(100) NOT NULL,
                    link TEXT NOT NULL,
                    name VARCHAR(500) NOT NULL,
                    sku VARCHAR(100) NULL,
                    link_hash CHAR(64) NULL,
                    tech_specs JSON,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    datasheet_link TEXT,
                    image_url TEXT,
                    ai_processed TINYINT(1) DEFAULT 0,
                    ai_processed_at TIMESTAMP NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """,
            'imprimantes_scanners': """
                CREATE TABLE IF NOT EXISTS imprimantes_scanners (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    brand VARCHAR(100) NOT NULL,
                    link TEXT NOT NULL,
                    name VARCHAR(500) NOT NULL,
                    sku VARCHAR(100) NULL,
                    link_hash CHAR(64) NULL,
                    tech_specs JSON,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    datasheet_link TEXT,
                    image_url TEXT,
                    ai_processed TINYINT(1) DEFAULT 0,
                    ai_processed_at TIMESTAMP NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """
        }
        
        try:
            cursor = self.connection.cursor()
            for table_name, query in tables.items():
                cursor.execute(query)
                logger.info(f"✅ Table '{table_name}' créée/vérifiée")
                # Migration légère: ajouter colonnes/index si table existait déjà
                self._migrate_table_schema(cursor, table_name)
            
            self.connection.commit()
            cursor.close()
            
        except Error as e:
            logger.error(f"❌ Erreur création tables: {e}")

    def _migrate_table_schema(self, cursor, table_name: str):
        """Ajoute les colonnes/index si manquants et ajuste les clés uniques pour un upsert robuste."""
        # Colonnes à ajouter
        alter_statements = [
            f"ALTER TABLE {table_name} ADD COLUMN sku VARCHAR(100) NULL",
            f"ALTER TABLE {table_name} ADD COLUMN link_hash CHAR(64) NULL",
            f"ALTER TABLE {table_name} ADD COLUMN ai_processed TINYINT(1) DEFAULT 0",
            f"ALTER TABLE {table_name} ADD COLUMN ai_processed_at TIMESTAMP NULL",
            f"ALTER TABLE {table_name} ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1",
            f"ALTER TABLE {table_name} ADD COLUMN last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        ]
        for stmt in alter_statements:
            try:
                cursor.execute(stmt)
                logger.info(f"🔧 {table_name}: colonne ajoutée ({stmt})")
            except Error as e:
                # Ignorer si la colonne existe déjà
                if 'Duplicate column name' in str(e):
                    pass
                else:
                    logger.debug(f"ℹ️ Ignoré: {e}")

        # Indices uniques: remplacer (brand, name) par (brand, sku) et (brand, link_hash)
        try:
            cursor.execute(f"ALTER TABLE {table_name} DROP INDEX unique_product")
            logger.info(f"🔧 {table_name}: index unique_product supprimé")
        except Error:
            pass

        # Ajouter unique(brand, sku)
        try:
            cursor.execute(f"CREATE UNIQUE INDEX unique_brand_sku ON {table_name} (brand, sku)")
            logger.info(f"🔧 {table_name}: index unique_brand_sku créé")
        except Error as e:
            if 'Duplicate key name' in str(e):
                pass
            else:
                logger.warning(f"⚠️ {table_name}: création unique_brand_sku ignorée: {e}")

        # Ajouter unique(brand, link_hash) pour dédup sans SKU
        try:
            cursor.execute(f"CREATE UNIQUE INDEX unique_brand_linkhash ON {table_name} (brand, link_hash)")
            logger.info(f"🔧 {table_name}: index unique_brand_linkhash créé")
        except Error as e:
            if 'Duplicate key name' in str(e):
                pass
            else:
                logger.warning(f"⚠️ {table_name}: création unique_brand_linkhash ignorée: {e}")
    
    def insert_products(self, products_data, table_name):
        """
        Insère les produits dans la table spécifiée
        """
        if not self.connection or not self.connection.is_connected():
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            
            # Requête d'insertion avec gestion des doublons (clé: brand+sku ou brand+link_hash)
            query = f"""
                INSERT INTO {table_name}
                (brand, link, name, sku, link_hash, tech_specs, scraped_at, datasheet_link, image_url, ai_processed, ai_processed_at, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    tech_specs = VALUES(tech_specs),
                    scraped_at = VALUES(scraped_at),
                    datasheet_link = VALUES(datasheet_link),
                    image_url = VALUES(image_url),
                    ai_processed = VALUES(ai_processed),
                    ai_processed_at = VALUES(ai_processed_at),
                    is_active = 1,
                    last_seen = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            inserted_count = 0
            updated_count = 0
            
            for product in products_data:
                # Conversion des tech_specs en JSON string
                tech_specs_json = json.dumps(product.get('tech_specs', {}), ensure_ascii=False)
                link_val = product.get('link', '') or ''
                link_hash = hashlib.sha256(link_val.encode('utf-8')).hexdigest() if link_val else None
                ai_processed = 1 if product.get('ai_processed') else 0
                ai_processed_at = product.get('ai_processed_at')
                
                values = (
                    product.get('brand', ''),
                    link_val,
                    product.get('name', ''),
                    product.get('sku'),
                    link_hash,
                    tech_specs_json,
                    product.get('scraped_at', datetime.now().isoformat()),
                    product.get('datasheet_link'),
                    product.get('image_url', ''),
                    ai_processed,
                    ai_processed_at,
                    1
                )
                
                # Vérifier si le produit existe déjà (préfère SKU, sinon link_hash)
                check_query = f"SELECT id FROM {table_name} WHERE brand = %s AND ((sku IS NOT NULL AND sku = %s) OR (sku IS NULL AND link_hash = %s)) LIMIT 1"
                cursor.execute(check_query, (product.get('brand'), product.get('sku'), link_hash))
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

    def deactivate_missing(self, table_name: str, brand: str, current_skus: set, current_link_hashes: set):
        """Marque inactifs les produits d'une marque non présents dans le lot courant (par SKU ou link_hash)."""
        if not self.connection or not self.connection.is_connected():
            self.connect()

        if not brand:
            logger.warning("⚠️ deactivate_missing: brand non spécifié, opération ignorée")
            return

        try:
            cursor = self.connection.cursor()

            # Réactiver les actuels (sécurité si relance)
            if current_skus:
                sku_list = ','.join(['%s'] * len(current_skus))
                cursor.execute(
                    f"UPDATE {table_name} SET is_active = 1, last_seen = CURRENT_TIMESTAMP WHERE brand = %s AND sku IN ({sku_list})",
                    (brand, *list(current_skus))
                )

            if current_link_hashes:
                lh_list = ','.join(['%s'] * len(current_link_hashes))
                cursor.execute(
                    f"UPDATE {table_name} SET is_active = 1, last_seen = CURRENT_TIMESTAMP WHERE brand = %s AND (sku IS NULL OR sku = '') AND link_hash IN ({lh_list})",
                    (brand, *list(current_link_hashes))
                )

            # Désactiver ceux non vus avec SKU
            if current_skus:
                sku_list = ','.join(['%s'] * len(current_skus))
                cursor.execute(
                    f"UPDATE {table_name} SET is_active = 0 WHERE brand = %s AND sku IS NOT NULL AND sku <> '' AND sku NOT IN ({sku_list})",
                    (brand, *list(current_skus))
                )
            else:
                # Aucun SKU dans ce lot: ne pas désactiver en masse par SKU
                pass

            # Désactiver ceux non vus sans SKU (par link_hash)
            if current_link_hashes:
                lh_list = ','.join(['%s'] * len(current_link_hashes))
                cursor.execute(
                    f"UPDATE {table_name} SET is_active = 0 WHERE brand = %s AND (sku IS NULL OR sku = '') AND link_hash IS NOT NULL AND link_hash <> '' AND link_hash NOT IN ({lh_list})",
                    (brand, *list(current_link_hashes))
                )

            self.connection.commit()
            cursor.close()
            logger.info(f"🟡 {table_name}:{brand} - désactivation des produits non vus terminée")
        except Error as e:
            logger.error(f"❌ Erreur désactivation des produits manquants: {e}")

def save_to_database(json_file_path, table_name, brand_filter=None):
    """
    Fonction utilitaire pour sauvegarder un fichier JSON en base
    """
    db = None
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

        # Désactiver les produits non vus de la même marque (si brand_filter fourni et si activé)
        enable_deactivate = os.getenv('ENABLE_DEACTIVATE_MISSING', 'true').lower() == 'true'
        if brand_filter and enable_deactivate:
            current_skus = {p.get('sku') for p in products_data if p.get('sku')}
            current_link_hashes = set()
            for p in products_data:
                link_val = p.get('link') or ''
                if link_val:
                    current_link_hashes.add(hashlib.sha256(link_val.encode('utf-8')).hexdigest())
            db.deactivate_missing(table_name, brand_filter, current_skus, current_link_hashes)
        elif brand_filter and not enable_deactivate:
            logger.info(f"⏭️ Désactivation des produits non vus SKIPPED (ENABLE_DEACTIVATE_MISSING=false) pour {table_name}:{brand_filter}")

        logger.info(f"✅ Sauvegarde terminée: {inserted} insertions, {updated} mises à jour")
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
    finally:
        if db:
            db.close()

if __name__ == "__main__":
    # Test de connexion
    db = MySQLConnector()
    db.create_database()
    if db.connect():
        db.create_tables()
        db.close()