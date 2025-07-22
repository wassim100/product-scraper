#!/usr/bin/env python3
"""
Script de test pour le module Gemini AI optimisé.
"""

import json
import os
from ai_processing.gemini_cleaning import GeminiProcessor, process_json_file

# --- CONFIGURATION ---
# Remplacez par votre clé API si elle n'est pas définie en variable d'environnement
API_KEY = os.getenv('GEMINI_API_KEY', "AIzaSyAXlHUspVmO-IwLWg63yJ3U7l32eMxQweg") 
INPUT_JSON = 'asus_servers_full.json'
OUTPUT_JSON = 'asus_servers_gemini_test_output.json'

def test_single_product_processing():
    """
    Teste le traitement d'un seul produit pour vérifier la logique de nettoyage.
    """
    print("🧪 === Test 1: Traitement d'un produit unique ===")
    
    # Initialiser le processeur en mode économe (par défaut)
    try:
        processor = GeminiProcessor(api_key=API_KEY)
        print(f"✅ Processeur Gemini initialisé avec le modèle '{processor.model._model_name}'.")
    except Exception as e:
        print(f"❌ Erreur d'initialisation du processeur : {e}")
        return

    # Exemple de spécifications brutes (similaire à ce que le scraper extrait)
    sample_specs = {
        "General": "Powered by Intel Xeon E-2300 series processors, four DDR4 DIMM slots, two M.2 slots, up to four 3.5-inch HDDs, and one 2.5-inch SSD.",
        "Redundancy": "Includes dual redundant power supplies for high availability."
    }
    product_name = "Serveur de Test"

    print(f"\n🤖 Traitement des spécifications pour '{product_name}'...")
    
    cleaned_specs = processor.clean_tech_specs(sample_specs, product_name)

    print("\n--- RÉSULTAT ---")
    print("Spécifications brutes :")
    print(json.dumps(sample_specs, indent=2))
    print("\nSpécifications nettoyées par Gemini :")
    print(json.dumps(cleaned_specs, indent=2, ensure_ascii=False))

    if "error" in cleaned_specs:
        print("\n❌ Le test a rencontré une erreur.")
    else:
        print("\n✅ Le test sur un produit unique est réussi !")

def test_full_file_processing():
    """
    Teste le traitement d'un fichier JSON complet, comme dans le vrai workflow.
    """
    print("\n🧪 === Test 2: Traitement d'un fichier JSON complet ===")
    
    # Créer un fichier de test avec les 2 premiers produits pour économiser les jetons
    try:
        if not os.path.exists(INPUT_JSON):
            print(f"❌ Fichier d'entrée '{INPUT_JSON}' non trouvé. Test annulé.")
            return
            
        with open(INPUT_JSON, 'r', encoding='utf-8') as f:
            all_products = json.load(f)
        
        test_products = all_products[:2]
        test_input_file = 'asus_servers_gemini_test_input.json'
        with open(test_input_file, 'w', encoding='utf-8') as f:
            json.dump(test_products, f, indent=2)
        
        print(f"✅ Fichier de test créé avec {len(test_products)} produits : '{test_input_file}'")
    except Exception as e:
        print(f"❌ Erreur lors de la création du fichier de test : {e}")
        return

    print(f"\n🤖 Lancement du traitement complet sur '{test_input_file}'...")
    
    # Appeler la fonction principale de traitement de fichier
    process_json_file(
        input_file=test_input_file,
        output_file=OUTPUT_JSON,
        api_key=API_KEY
    )

    print(f"\n--- RÉSULTAT ---")
    try:
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print(f"✅ Fichier de sortie '{OUTPUT_JSON}' généré avec succès.")
        print("Contenu du premier produit traité :")
        print(json.dumps(results[0], indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du fichier de sortie : {e}")

if __name__ == "__main__":
    test_single_product_processing()
    test_full_file_processing()
