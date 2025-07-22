"""
Test du scraper XFusion amélioré avec extraction des spécifications détaillées
"""

import sys
import os
import json
import logging

# Ajouter le répertoire serveurs au path
sys.path.append(os.path.join(os.path.dirname(__file__), 'serveurs'))

from xfusion import XFusionServerScraperImproved

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_enhanced_specs_extraction():
    """Test du scraper avec extraction des spécifications détaillées"""
    
    scraper = XFusionServerScraperImproved()
    
    try:
        scraper.setup_driver()
        
        # Test sur les AI Servers pour voir les spécifications détaillées
        url = "https://www.xfusion.com/en/product/heterogeneous-server"
        
        print("🔍 Test extraction AI Servers avec spécifications détaillées...")
        servers = scraper.extract_table_servers_improved(url, "AI Servers")
        
        if servers:
            # Sauvegarder les résultats
            with open('test_detailed_specs.json', 'w', encoding='utf-8') as f:
                json.dump(servers, f, indent=2, ensure_ascii=False)
            
            print(f"\n📊 RÉSULTATS DU TEST AMÉLIORÉ:")
            print(f"Serveurs trouvés: {len(servers)}")
            
            # Compter les éléments extraits
            datasheet_count = sum(1 for s in servers if s.get('datasheet_link'))
            image_count = sum(1 for s in servers if s.get('image_url'))
            detailed_specs_count = sum(1 for s in servers if len(s.get('tech_specs', {})) > 5)
            
            print(f"📄 Datasheets extraits: {datasheet_count}/{len(servers)}")
            print(f"🖼️ Images extraites: {image_count}/{len(servers)}")
            print(f"🔧 Spécifications détaillées: {detailed_specs_count}/{len(servers)}")
            
            # Afficher des exemples de spécifications détaillées
            print(f"\n🔍 EXEMPLES DE SPÉCIFICATIONS DÉTAILLÉES:")
            for i, server in enumerate(servers[:2], 1):
                print(f"\n✅ Serveur {i}: {server['name']}")
                print(f"   Lien: {server['link']}")
                print(f"   Datasheet: {server['datasheet_link'][:50] + '...' if server['datasheet_link'] else 'Non trouvé'}")
                print(f"   Image: {server['image_url'][:50] + '...' if server['image_url'] else 'Non trouvée'}")
                
                # Afficher les spécifications techniques
                specs = server.get('tech_specs', {})
                print(f"   Spécifications ({len(specs)} éléments):")
                
                if len(specs) <= 5:
                    # Spécifications basiques (anciennes)
                    print("     ⚠️ Spécifications basiques (limitées):")
                    for key, value in specs.items():
                        print(f"       {key}: {value}")
                else:
                    # Spécifications détaillées (nouvelles)
                    print("     ✅ Spécifications détaillées (complètes):")
                    for key, value in list(specs.items())[:5]:
                        print(f"       {key}: {value}")
                    if len(specs) > 5:
                        print(f"       ... et {len(specs) - 5} autres spécifications")
                
        else:
            print("❌ Aucun serveur trouvé")
            
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        
    finally:
        if scraper.driver:
            scraper.driver.quit()

if __name__ == "__main__":
    test_enhanced_specs_extraction()
