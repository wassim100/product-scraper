"""
Debug script pour analyser la structure du site Lenovo
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def debug_lenovo_structure():
    """Analyser la structure HTML du site Lenovo"""
    
    # Configuration Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Test avec l'URL des serveurs Lenovo
        url = "https://www.lenovo.com/us/en/servers-storage/servers/"
        print(f"🔍 Analyse de la page Lenovo: {url}")
        
        driver.get(url)
        time.sleep(8)  # Attendre le chargement complet
        
        # Gérer les cookies
        print("\n🍪 GESTION DES COOKIES:")
        try:
            cookie_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'I Accept')]")
            if cookie_buttons:
                cookie_buttons[0].click()
                time.sleep(2)
                print("  ✅ Cookie banner fermé")
            else:
                print("  ℹ️ Pas de cookie banner trouvé")
        except Exception as e:
            print(f"  ⚠️ Erreur cookies: {e}")
        
        # Analyser le titre de la page
        page_title = driver.title
        print(f"\n📄 TITRE DE LA PAGE: {page_title}")
        
        # Vérifier si la page a du contenu
        page_source_length = len(driver.page_source)
        print(f"📏 Taille du code source: {page_source_length} caractères")
        
        # Chercher différents types d'éléments produits
        print("\n🔍 RECHERCHE D'ÉLÉMENTS PRODUITS:")
        
        selectors_to_test = [
            (".product-card", "Product Cards"),
            (".product-item", "Product Items"),
            (".product-tile", "Product Tiles"),
            (".server-product", "Server Products"),
            ("[data-testid*='product']", "Data-testid Products"),
            (".facetedResults-item", "Faceted Results"),
            (".product", "Generic Products"),
            (".card", "Cards"),
            (".item", "Items"),
            (".grid-item", "Grid Items"),
            (".product-list-item", "Product List Items"),
            (".server-item", "Server Items")
        ]
        
        for selector, description in selectors_to_test:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"  {description} ({selector}): {len(elements)} éléments")
                
                # Si on trouve des éléments, examiner le premier
                if elements and len(elements) > 0:
                    first_elem = elements[0]
                    # Chercher du texte qui pourrait être un nom de produit
                    text_content = first_elem.text.strip()[:100]
                    if text_content:
                        print(f"    Exemple de contenu: {text_content}")
                    
                    # Chercher des liens
                    links = first_elem.find_elements(By.TAG_NAME, "a")
                    if links:
                        href = links[0].get_attribute('href')
                        print(f"    Exemple de lien: {href}")
                        
            except Exception as e:
                print(f"  Erreur avec {selector}: {e}")
        
        # Chercher des éléments spécifiques à Lenovo
        print("\n🏢 ÉLÉMENTS SPÉCIFIQUES LENOVO:")
        
        lenovo_selectors = [
            ".think-system",
            ".thinksystem",
            ".server",
            "[class*='server']",
            "[class*='think']",
            ".product-name",
            ".product-title",
            "h3",
            "h4",
            ".title"
        ]
        
        for selector in lenovo_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"  {selector}: {len(elements)} éléments")
                    # Afficher quelques exemples de texte
                    for i, elem in enumerate(elements[:3]):
                        text = elem.text.strip()
                        if text and len(text) > 3:
                            print(f"    {i+1}. {text[:80]}")
                            
            except:
                continue
        
        # Analyser les classes CSS présentes
        print("\n🎨 CLASSES CSS PRINCIPALES:")
        elements_with_classes = driver.find_elements(By.XPATH, "//*[@class]")
        classes_count = {}
        for elem in elements_with_classes:
            classes = elem.get_attribute('class')
            if classes:
                for cls in classes.split():
                    if any(keyword in cls.lower() for keyword in ['product', 'server', 'think', 'card', 'item']):
                        classes_count[cls] = classes_count.get(cls, 0) + 1
        
        for cls, count in sorted(classes_count.items(), key=lambda x: x[1], reverse=True)[:15]:
            print(f"  {cls}: {count}")
        
        # Vérifier le contenu de la page
        print("\n📝 ANALYSE DU CONTENU:")
        page_source = driver.page_source.lower()
        
        keywords = ['thinksystem', 'server', 'product', 'thinkagile', 'rack', 'tower']
        for keyword in keywords:
            count = page_source.count(keyword)
            print(f"  '{keyword}': {count} occurrences")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_lenovo_structure()
