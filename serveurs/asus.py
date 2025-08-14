from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
import json
import os
import time
import re
import sys

# Ajouter le chemin du module database
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.mysql_connector import save_to_database
ENABLE_DB = os.getenv("ENABLE_DB", "false").lower() == "true"

# ✅ Paramètres
CHROMEDRIVER_PATH = os.path.join(os.getcwd(), "chromedriver.exe")
URL = "https://servers.asus.com/products/Servers"
BASE = "https://servers.asus.com"
OUTPUT_JSON = "asus_servers_full.json"

# Configuration pour tests rapides
MAX_PAGES_TO_SCRAPE = 2  # ⚡ SEULEMENT 2 PAGES pour test rapide
DELAY_BETWEEN_PRODUCTS = 1  # 1 seconde entre produits
DELAY_BETWEEN_PAGES = 2     # 2 secondes entre pages

# Configuration pour tests rapides
MAX_PAGES_TO_SCRAPE = 2  # ⚡ SEULEMENT 2 PAGES pour test rapide
DELAY_BETWEEN_PRODUCTS = 1  # 1 seconde entre produits
DELAY_BETWEEN_PAGES = 2     # 2 secondes entre pages

# ✅ Config navigateur avec options améliorées pour éviter la détection
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
options.add_argument("--disable-logging")
options.add_argument("--disable-gpu-sandbox")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# Délais plus longs pour éviter la détection
wait = WebDriverWait(driver, 30)
driver.implicitly_wait(10)

# ✅ Fonction pour extraire les spécifications techniques d'un produit
def extract_product_specs(driver, wait, product_link):
    """Extrait les spécifications techniques d'un produit"""
    try:
        driver.get(product_link)
        
        # Attendre le chargement de la page
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)
        
        specs_dict = {}
        
        # Méthode 1 : Recherche dans les tableaux de spécifications
        try:
            spec_sections = driver.find_elements(By.CSS_SELECTOR, ".specifications, .spec-table, .tech-specs, table")
            for section in spec_sections:
                rows = section.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 2:
                        key = cols[0].text.strip()
                        value = cols[1].text.strip()
                        if key and value:
                            specs_dict[key] = value
        except:
            pass
        
        # Méthode 2 : Recherche dans les divs avec classes spécifiques
        try:
            spec_divs = driver.find_elements(By.CSS_SELECTOR, ".spec-item, .specification-item, .feature-item")
            for div in spec_divs:
                try:
                    label = div.find_element(By.CSS_SELECTOR, ".label, .spec-label, .title, h4, strong").text.strip()
                    value = div.find_element(By.CSS_SELECTOR, ".value, .spec-value, .description, p, span").text.strip()
                    if label and value:
                        specs_dict[label] = value
                except:
                    continue
        except:
            pass
        
        # Méthode 3 : Recherche générale de texte structuré
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            # Recherche de patterns comme "Processeur: Intel Xeon" 
            patterns = [
                r'([^:\n]+):\s*([^\n]+)',
                r'([^-\n]+)-\s*([^\n]+)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, page_text, re.MULTILINE)
                for match in matches:
                    key, value = match[0].strip(), match[1].strip()
                    if (len(key) < 50 and len(value) < 200 and 
                        not any(x in key.lower() for x in ['http', 'www', 'click', 'more']) and
                        any(x in key.lower() for x in ['processor', 'memory', 'storage', 'network', 'power', 'dimension'])):
                        specs_dict[key] = value
        except:
            pass
        
        # Recherche du lien datasheet
        datasheet_link = None
        try:
            pdf_links = driver.find_elements(By.XPATH, "//a[contains(@href,'.pdf') or contains(text(),'datasheet') or contains(text(),'specification')]")
            if pdf_links:
                datasheet_link = pdf_links[0].get_attribute("href")
        except:
            pass
        
        # Recherche de l'image principale
        image_url = ""
        try:
            # Plusieurs sélecteurs possibles pour l'image
            image_selectors = [
                ".product-image img",
                ".main-image img", 
                ".hero-image img",
                "img[src*='product']",
                ".gallery img"
            ]
            for selector in image_selectors:
                try:
                    img_element = driver.find_element(By.CSS_SELECTOR, selector)
                    image_url = img_element.get_attribute("src")
                    if image_url:
                        break
                except:
                    continue
        except:
            pass
        
        return specs_dict, datasheet_link, image_url
        
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction des specs: {e}")
        return {}, None, ""

# ✅ Fonction pour extraire tous les produits avec pagination
def extract_all_products(driver, wait, base_url):
    """Extrait tous les produits en gérant la pagination"""
    all_products = []
    current_page = 1
    max_pages = MAX_PAGES_TO_SCRAPE  # Utiliser la config
    
    print(f"🔍 Extraction avec limite de {max_pages} pages (modifiez MAX_PAGES_TO_SCRAPE pour plus)")
    
    # Aller à la première page
    driver.get(base_url)
    time.sleep(3)
    
    while current_page <= max_pages:
        print(f"📄 Scraping page {current_page}/{max_pages}...")
        
        try:
            # Attendre le chargement des produits
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)
            
            # Essayer de détecter les produits
            product_items = driver.find_elements(By.CLASS_NAME, "product_box_item")
            
            # Si pas de produits avec ce sélecteur, essayer d'autres
            if not product_items:
                # Autres sélecteurs possibles pour ASUS
                alternative_selectors = [
                    ".product-item",
                    ".server-item", 
                    ".product-card",
                    "[data-testid='product']",
                    ".product",
                    ".product-box",
                    ".item"
                ]
                
                for selector in alternative_selectors:
                    product_items = driver.find_elements(By.CSS_SELECTOR, selector)
                    if product_items:
                        print(f"✅ Produits trouvés avec sélecteur: {selector}")
                        break
            
            if not product_items:
                print(f"❌ Aucun produit trouvé sur la page {current_page}")
                break
            
            print(f"🔍 {len(product_items)} produits trouvés sur la page {current_page}")
            
            # Traiter les produits de cette page
            page_products = extract_products_from_page(driver, wait, product_items, current_page)
            all_products.extend(page_products)
            
            print(f"✅ Page {current_page} terminée - Total produits: {len(all_products)}")
            
            # Ne pas chercher la page suivante si on a atteint la limite
            if current_page >= max_pages:
                print(f"🛑 Limite de pages atteinte ({max_pages})")
                break
            
            # Vérifier s'il y a une page suivante
            has_next_page = check_next_page(driver)
            if not has_next_page:
                print(f"✅ Dernière page atteinte (page {current_page})")
                break
            
            # Pause entre les pages
            print(f"⏳ Pause de {DELAY_BETWEEN_PAGES}s entre les pages...")
            time.sleep(DELAY_BETWEEN_PAGES)
            
            # Naviguer vers la page suivante
            if not navigate_to_next_page(driver):
                print(f"❌ Impossible de naviguer vers la page suivante")
                break
                
            current_page += 1
            
        except Exception as e:
            print(f"❌ Erreur sur la page {current_page}: {e}")
            break
    
    print(f"🎯 Extraction terminée - {len(all_products)} produits au total")
    return all_products

def check_next_page(driver):
    """Vérifie s'il y a une page suivante"""
    try:
        # Méthode 1 : Chercher le bouton "suivant" ou numéro de page suivant
        next_selectors = [
            ".pagination .next:not(.disabled)",
            ".pagination a[aria-label='Next']:not(.disabled)",
            ".page-next:not(.disabled)",
            ".pagination-next:not(.disabled)",
            "button[title='Next']:not(.disabled)",
            ".fa-chevron-right:not(.disabled)",
            ".arrow-right:not(.disabled)"
        ]
        
        for selector in next_selectors:
            next_elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if next_elements and next_elements[0].is_enabled():
                print(f"✅ Page suivante détectée avec sélecteur: {selector}")
                return True
        
        # Méthode 2 : Vérifier les numéros de page
        page_links = driver.find_elements(By.CSS_SELECTOR, ".pagination a, .page-number")
        current_page_elements = driver.find_elements(By.CSS_SELECTOR, ".pagination .active, .pagination .current, .current-page")
        
        if page_links and current_page_elements:
            # Extraire le numéro de page actuel
            try:
                current_page_text = current_page_elements[0].text.strip()
                current_page_num = int(current_page_text)
                
                # Chercher s'il y a une page suivante dans les liens
                for link in page_links:
                    link_text = link.text.strip()
                    if link_text.isdigit() and int(link_text) > current_page_num:
                        print(f"✅ Page suivante trouvée: {link_text}")
                        return True
            except ValueError:
                pass
        
        # Méthode 3 : Méthode générale - chercher des éléments de pagination
        pagination_container = driver.find_elements(By.CSS_SELECTOR, ".pagination, .pager, .page-navigation")
        if pagination_container:
            # Chercher tous les liens dans la pagination
            all_links = pagination_container[0].find_elements(By.TAG_NAME, "a")
            clickable_links = [link for link in all_links if link.is_enabled() and link.text.strip()]
            
            if len(clickable_links) > 1:
                print(f"✅ {len(clickable_links)} liens de pagination trouvés")
                return True
        
        print("❌ Aucune page suivante détectée")
        return False
        
    except Exception as e:
        print(f"⚠️ Erreur lors de la vérification de pagination: {e}")
        return False

def navigate_to_next_page(driver):
    """Navigue vers la page suivante"""
    try:
        # Essayer de cliquer sur le bouton suivant
        next_selectors = [
            ".pagination .next:not(.disabled)",
            ".pagination a[aria-label='Next']:not(.disabled)", 
            ".page-next:not(.disabled)"
        ]
        
        for selector in next_selectors:
            next_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            if next_buttons and next_buttons[0].is_enabled():
                driver.execute_script("arguments[0].click();", next_buttons[0])
                time.sleep(3)
                return True
        
        # Si pas de bouton "suivant", essayer de trouver le numéro de page suivant
        current_page_elements = driver.find_elements(By.CSS_SELECTOR, ".pagination .active, .pagination .current")
        if current_page_elements:
            current_page_text = current_page_elements[0].text.strip()
            if current_page_text.isdigit():
                next_page_num = int(current_page_text) + 1
                next_page_link = driver.find_elements(By.XPATH, f"//a[text()='{next_page_num}']")
                if next_page_link:
                    driver.execute_script("arguments[0].click();", next_page_link[0])
                    time.sleep(3)
                    return True
        
        return False
        
    except Exception as e:
        print(f"❌ Erreur navigation page suivante: {e}")
        return False

def extract_products_from_page(driver, wait, product_items, page_num):
    """Extrait les produits d'une page donnée"""
    page_products = []
    
    for index, item in enumerate(product_items):
        try:
            # Extraction du nom
            name_element = item.find_element(By.TAG_NAME, "h2")
            name = name_element.text.strip()
            
            # Extraction du lien
            link_element = item.find_element(By.TAG_NAME, "a")
            relative_url = link_element.get_attribute("href")
            product_link = relative_url if relative_url.startswith("http") else BASE + relative_url

            print(f"📦 [Page {page_num}] [{index+1}/{len(product_items)}] Traitement de {name}...")

            # Gestion d'erreurs plus robuste
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Accéder à la page produit dans un nouvel onglet
                    driver.execute_script("window.open('');")
                    driver.switch_to.window(driver.window_handles[1])
                    
                    # Utiliser la fonction d'extraction améliorée
                    specs_dict, datasheet_link, image_url = extract_product_specs(driver, wait, product_link)
                    
                    # Si pas d'image trouvée, essayer l'image de la liste
                    if not image_url:
                        try:
                            driver.switch_to.window(driver.window_handles[0])
                            image_url = item.find_element(By.TAG_NAME, "img").get_attribute("src")
                            driver.switch_to.window(driver.window_handles[1])
                        except:
                            image_url = ""
                    
                    # ✅ Ajout à la liste selon le schéma du cahier des charges
                    product_data = {
                        "brand": "Asus",
                        "link": product_link,
                        "name": name,
                        "tech_specs": specs_dict,
                        "scraped_at": datetime.now().isoformat(),
                        "datasheet_link": datasheet_link,
                        "image_url": image_url
                    }
                    
                    page_products.append(product_data)
                    print(f"✅ [Page {page_num}] [{index+1}/{len(product_items)}] {name} - {len(specs_dict)} spécifications extraites")
                    break  # Succès, sortir de la boucle de retry
                    
                except Exception as e:
                    retry_count += 1
                    print(f"⚠️ Tentative {retry_count}/{max_retries} échouée pour {name}: {e}")
                    
                    if retry_count < max_retries:
                        # Fermer tous les onglets supplémentaires et attendre
                        while len(driver.window_handles) > 1:
                            driver.switch_to.window(driver.window_handles[-1])
                            driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        
                        print(f"🔄 Attente de {retry_count * 5} secondes avant retry...")
                        time.sleep(retry_count * 5)  # Attente progressive
                    else:
                        # Dernier échec, ajouter le produit avec infos minimales
                        print(f"❌ Échec définitif pour {name}, ajout avec infos de base")
                        page_products.append({
                            "brand": "Asus",
                            "link": product_link,
                            "name": name,
                            "tech_specs": {},
                            "scraped_at": datetime.now().isoformat(),
                            "datasheet_link": None,
                            "image_url": ""
                        })

            # Nettoyer : fermer l'onglet et revenir à la liste
            try:
                while len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.close()
                driver.switch_to.window(driver.window_handles[0])
            except:
                pass
            
            # Pause pour éviter la surcharge (plus longue entre les produits)
            time.sleep(DELAY_BETWEEN_PRODUCTS)

        except Exception as e:
            print(f"❌ Erreur critique sur produit {index+1} de la page {page_num}: {e}")
            try:
                while len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.close()
                driver.switch_to.window(driver.window_handles[0])
            except:
                pass
            continue
    
    return page_products

# ✅ Étape 1 : Extraire tous les produits avec pagination
print("🚀 Démarrage de l'extraction avec gestion de pagination...")
products_data = extract_all_products(driver, wait, URL)

driver.quit()

# ✅ Export JSON
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(products_data, f, ensure_ascii=False, indent=4)

print(f"\n🎯 Extraction terminée. {len(products_data)} produits enregistrés → {OUTPUT_JSON}")

# ✅ Sauvegarde en base de données MySQL
if ENABLE_DB:
    print("\n💾 Sauvegarde en base de données...")
    try:
        save_to_database(OUTPUT_JSON, "serveurs", "Asus")
        print("✅ Sauvegarde en base de données réussie!")
    except Exception as e:
        print(f"❌ Erreur sauvegarde base de données: {e}")
        print("💡 Assurez-vous que MySQL est installé et configuré")
else:
    print("💾 Sauvegarde BD désactivée (ENABLE_DB=false)")
