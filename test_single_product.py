"""
Test simple d'extraction de spécifications détaillées depuis une page produit
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def test_single_product_specs():
    """Test d'extraction des spécifications pour un produit spécifique"""
    
    # Configuration Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Test avec FusionServer G5500 V6
        url = "https://www.xfusion.com/en/product/heterogeneous-server/fusionserver-g5500-v6"
        print(f"🔍 Test d'extraction des spécifications pour: {url}")
        
        driver.get(url)
        time.sleep(5)
        
        # Cliquer sur l'onglet "Technical Specifications"
        try:
            tech_specs_tab = driver.find_element(By.XPATH, "//a[contains(text(), 'Technical Specifications')]")
            driver.execute_script("arguments[0].click();", tech_specs_tab)
            time.sleep(3)
            print("✅ Clic sur l'onglet Technical Specifications réussi")
        except Exception as e:
            print(f"⚠️ Impossible de cliquer sur Technical Specifications: {e}")
        
        # Extraire les spécifications depuis le tableau
        specs = {}
        
        try:
            # Chercher le tableau des spécifications
            tables = driver.find_elements(By.TAG_NAME, "table")
            print(f"📊 Nombre de tableaux trouvés: {len(tables)}")
            
            for i, table in enumerate(tables):
                print(f"\n🔍 Analyse du tableau {i+1}:")
                rows = table.find_elements(By.TAG_NAME, "tr")
                print(f"   Nombre de lignes: {len(rows)}")
                
                # Examiner les premières lignes pour identifier le bon tableau
                for j, row in enumerate(rows[:3]):
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        param = cells[0].text.strip()
                        description = cells[1].text.strip()
                        print(f"   Ligne {j+1}: '{param}' = '{description}'")
                        
                        if param and description and param != "Parameter":
                            specs[param] = description
            
            print(f"\n✅ Spécifications extraites: {len(specs)}")
            for key, value in list(specs.items())[:10]:
                print(f"  {key}: {value}")
            
            if len(specs) > 10:
                print(f"  ... et {len(specs) - 10} autres spécifications")
                
        except Exception as e:
            print(f"❌ Erreur lors de l'extraction: {e}")
        
        # Vérifier si on peut voir du contenu de spécifications
        page_text = driver.page_source
        if "Form Factor" in page_text:
            print("\n✅ 'Form Factor' trouvé dans le code source")
        if "Processor" in page_text:
            print("✅ 'Processor' trouvé dans le code source")
        if "Parameter" in page_text:
            print("✅ 'Parameter' trouvé dans le code source")
        if "Description" in page_text:
            print("✅ 'Description' trouvé dans le code source")
        
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    test_single_product_specs()
