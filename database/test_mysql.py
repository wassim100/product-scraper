#!/usr/bin/env python3
"""
Script de test et configuration MySQL pour le projet de scraping
"""

import sys
import os

# Ajouter le chemin du module database
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from database.mysql_connector import MySQLConnector
import mysql.connector
from mysql.connector import Error

def test_mysql_connection():
    """Teste la connexion MySQL et diagnostique les problèmes"""
    print("🔍 Test de connexion MySQL...")
    
    try:
        # Test de base sans base de données
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password=''
        )
        connection.close()
        print("✅ MySQL est accessible avec l'utilisateur root sans mot de passe")
        return True
        
    except Error as e:
        print(f"❌ Erreur de connexion MySQL: {e}")
        
        if "Access denied" in str(e):
            print("💡 Solutions possibles:")
            print("   1. Vérifiez que MySQL est démarré")
            print("   2. Si vous utilisez XAMPP/WAMP: Démarrez MySQL depuis le panneau de contrôle")
            print("   3. Si MySQL a un mot de passe, modifiez database/config.py")
            print("   4. Essayez de vous connecter manuellement: mysql -u root -p")
            
        elif "Can't connect" in str(e):
            print("💡 MySQL semble ne pas être démarré:")
            print("   - Windows: Démarrez le service MySQL")
            print("   - XAMPP: Cliquez sur 'Start' pour MySQL")
            print("   - WAMP: Démarrez tous les services")
            
        return False

def test_database_operations():
    """Teste les opérations de base de données"""
    print("\n🔄 Test des opérations de base de données...")
    
    try:
        db = MySQLConnector()
        
        if not db.test_mysql_availability():
            return False
            
        if not db.connect():
            return False
            
        db.create_tables()
        print("✅ Tables créées avec succès")
        
        # Test d'insertion simple
        test_data = [{
            "brand": "Test Brand",
            "name": "Test Product",
            "link": "https://test.com",
            "tech_specs": {"spec1": "value1"},
            "scraped_at": "2024-01-01T00:00:00",
            "datasheet_link": "",
            "image_url": ""
        }]
        
        inserted, updated = db.insert_products(test_data, "stockage")
        print(f"✅ Test d'insertion: {inserted} insertions, {updated} mises à jour")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

def show_mysql_info():
    """Affiche des informations sur l'installation MySQL"""
    print("\n📋 Informations MySQL:")
    print("=" * 50)
    
    # Vérifier les services Windows
    print("🔍 Vérification des services MySQL...")
    try:
        import subprocess
        result = subprocess.run(['sc', 'query', 'mysql'], 
                              capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print("✅ Service MySQL détecté")
        else:
            print("⚠️ Service MySQL non trouvé")
            print("💡 Vous utilisez peut-être XAMPP/WAMP")
    except:
        print("⚠️ Impossible de vérifier les services")
    
    # Vérifier XAMPP
    xampp_paths = [
        "C:\\xampp\\mysql\\bin\\mysql.exe",
        "C:\\XAMPP\\mysql\\bin\\mysql.exe"
    ]
    
    for path in xampp_paths:
        if os.path.exists(path):
            print(f"✅ XAMPP MySQL trouvé: {path}")
            break
    else:
        print("ℹ️ XAMPP MySQL non détecté")

def main():
    print("🚀 Script de diagnostic MySQL")
    print("=" * 50)
    
    # Afficher les informations système
    show_mysql_info()
    
    # Tester la connexion
    if test_mysql_connection():
        # Si la connexion fonctionne, tester les opérations
        test_database_operations()
    else:
        print("\n❌ Impossible de se connecter à MySQL")
        print("💡 Vérifiez votre installation MySQL avant de continuer")

if __name__ == "__main__":
    main()
