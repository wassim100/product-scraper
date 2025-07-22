#!/usr/bin/env python3
"""
Test du scraper XFusion modifié avec filtrage des chassis et nodes
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'serveurs'))

from xfusion import XFusionServerScraperImproved
import json
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_filtered_scraper():
    """Test le scraper avec filtrage sur la catégorie AI Servers"""
    
    scraper = XFusionServerScraperImproved()
    
    logger.info("🚀 Test du scraper XFusion avec filtrage...")
    
    # Tester seulement la catégorie AI Servers pour validation rapide
    ai_servers_url = "https://www.xfusion.com/en/product/heterogeneous-server"
    
    scraper.setup_driver()
    
    try:
        logger.info("🔍 Extraction des AI Servers avec filtrage...")
        servers = scraper.extract_table_servers_improved(ai_servers_url, "AI Servers")
        
        logger.info(f"✅ Total serveurs après filtrage: {len(servers)}")
        
        # Afficher les résultats
        print("\n📊 SERVEURS EXTRAITS (après filtrage):")
        for i, server in enumerate(servers, 1):
            print(f"{i}. {server['name']}")
        
        # Sauvegarder les résultats
        output_file = "ai_servers_filtered_test.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(servers, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Résultats sauvegardés dans {output_file}")
        
        # Analyser les résultats
        print("\n🔍 ANALYSE DES RÉSULTATS:")
        
        # Vérifier qu'aucun chassis/node n'est présent
        filtered_items = []
        for server in servers:
            name_lower = server['name'].lower()
            if any(keyword in name_lower for keyword in ['chassis', 'node']):
                filtered_items.append(server['name'])
        
        if filtered_items:
            print(f"⚠️ ATTENTION: {len(filtered_items)} chassis/nodes trouvés:")
            for item in filtered_items:
                print(f"  - {item}")
        else:
            print("✅ Aucun chassis/node détecté - filtrage réussi!")
        
        # Compter les serveurs avec des spécifications détaillées
        detailed_specs_count = 0
        for server in servers:
            specs = server.get('tech_specs', {})
            # Vérifier si on a des spécifications riches (pas juste les colonnes de base)
            if any(len(str(value)) > 50 for value in specs.values()):
                detailed_specs_count += 1
        
        print(f"📈 Serveurs avec spécifications détaillées: {detailed_specs_count}/{len(servers)}")
        
        return servers
        
    finally:
        if scraper.driver:
            scraper.driver.quit()

if __name__ == "__main__":
    test_filtered_scraper()
