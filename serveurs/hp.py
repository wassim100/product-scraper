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

# --- CONFIGURATION HP ---
# On remplace l'URL unique par une liste d'URLs directes
URLS_TO_SCRAPE = [
    "https://www.hp.com/us-en/shop/mdp/smb-servers-3074457345617969168--1/tower-servers",
    "https://www.hp.com/us-en/shop/mdp/smb-servers-3074457345617969168--1/micro-servers",
    "https://www.hp.com/us-en/shop/mdp/smb-servers-3074457345617969168--1/rack-servers"
]
BASE_URL = "https://www.hp.com"
BRAND = "HP"
OUTPUT_JSON = "hp_servers_full.json"
CHROMEDRIVER_PATH = os.path.join(os.getcwd(), "chromedriver.exe")

# --- CONFIGURATION POUR LE TEST ---
# Ces délais sont conservés pour un scraping respectueux
DELAY_BETWEEN_PRODUCTS = 2
DELAY_BETWEEN_PAGES = 5 # Délai entre chaque catégorie

# --- SETUP SELENIUM ---
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.mysql_connector import save_to_database
ENABLE_DB = os.getenv("ENABLE_DB", "false").lower() == "true"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
wait = WebDriverWait(driver, 20)

# --- FONCTIONS DE SCRAPING (ADAPTÉES POUR HP) ---

def handle_cookie_banner(driver, wait):
    """Tente de trouver et de cliquer sur la bannière de cookies."""
    try:
        # HP utilise souvent OneTrust pour les cookies. On cible le bouton d'acceptation.
        cookie_button = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        print("INFO: Bannière de cookies trouvée. Clic sur 'Accept'.")
        cookie_button.click()
        time.sleep(2) # Laisser le temps à la page de se recharger/réorganiser après le clic.
    except TimeoutException:
        print("INFO: Pas de bannière de cookies trouvée avec l'ID 'onetrust-accept-btn-handler', ou déjà acceptée.")
    except Exception as e:
        print(f"AVERTISSEMENT: Erreur en essayant de gérer la bannière de cookies: {e}")

def handle_region_banner(driver, wait):
    """Tente de trouver et de cliquer sur la bannière de sélection de région."""
    try:
        # On cherche le bouton "NO THANKS" qui est dans un dialogue modal.
        # L'utilisation de XPath avec le texte est plus fiable ici.
        no_thanks_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'NO THANKS')]")))
        print("INFO: Bannière de région trouvée. Clic sur 'NO THANKS'.")
        no_thanks_button.click()
        time.sleep(2) # Laisser le temps au dialogue de se fermer.
    except TimeoutException:
        print("INFO: Pas de bannière de région trouvée, ou déjà fermée.")
    except Exception as e:
        print(f"AVERTISSEMENT: Erreur en essayant de gérer la bannière de région: {e}")


# La fonction extract_product_specs a été supprimée car elle n'est plus nécessaire avec l'approche JSON-LD

def scrape_category_page(driver, wait, category_url):
    """
    Extrait tous les produits d'une page de catégorie en utilisant une approche hybride :
    - Les liens depuis les éléments HTML
    - Les données depuis JSON-LD
    """
    page_products = []
    print(f"📄 Accès à la catégorie : {category_url}")
    driver.get(category_url)

    # GESTION DES POP-UPS
    handle_cookie_banner(driver, wait)
    handle_region_banner(driver, wait)

    try:
        # Attendre que la page soit chargée
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)  # Laisser le temps pour que tous les scripts s'exécutent

        # ÉTAPE 1: Extraire les liens des produits depuis les éléments HTML
        print("� Extraction des liens produits...")
        product_links_data = []
        
        # Chercher les conteneurs de produits avec des sélecteurs multiples
        product_containers = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid*="product"], div[class*="product"], div[class*="tile"], a[data-gtm-product-name]')
        
        for container in product_containers:
            try:
                # Essayer de trouver un lien dans le conteneur
                link_element = None
                product_name = ""
                
                # Si le conteneur est déjà un lien
                if container.tag_name == 'a':
                    link_element = container
                    product_name = container.get_attribute('data-gtm-product-name') or container.text.strip()
                else:
                    # Chercher un lien dans le conteneur
                    link_element = container.find_element(By.CSS_SELECTOR, "a")
                    product_name = link_element.get_attribute('data-gtm-product-name') or link_element.text.strip()
                
                if link_element:
                    href = link_element.get_attribute("href")
                    if href and href not in [item['link'] for item in product_links_data]:
                        product_links_data.append({
                            'link': href,
                            'name_hint': product_name
                        })
            except:
                continue
        
        print(f"🔗 {len(product_links_data)} liens de produits extraits")

        # ÉTAPE 2: Extraire les données depuis JSON-LD
        json_ld_scripts = driver.find_elements(By.XPATH, '//script[@type="application/ld+json"]')
        print(f"🔍 {len(json_ld_scripts)} balises de données structurées trouvées.")
        
        json_products = []
        
        for i, script in enumerate(json_ld_scripts):
            try:
                json_content = json.loads(script.get_attribute('innerHTML'))
                
                # DEBUG: Affichons la structure pour les premiers scripts
                if i < 2:
                    print(f"🔍 Script {i+1} structure: {list(json_content.keys()) if isinstance(json_content, dict) else type(json_content)}")
                    if isinstance(json_content, dict) and '@type' in json_content:
                        print(f"    @type: {json_content.get('@type')}")

                # Extraire les produits du JSON-LD
                if '@graph' in json_content:
                    for item in json_content['@graph']:
                        if item.get('@type') == 'Product':
                            json_products.append(item)
                elif json_content.get('@type') == 'Product':
                    json_products.append(json_content)
                elif json_content.get('@type') == 'ItemList':
                    items = json_content.get('itemListElement', [])
                    for item in items:
                        if isinstance(item, dict) and item.get('@type') == 'Product':
                            json_products.append(item)

            except json.JSONDecodeError:
                print(f"INFO: Script {i+1} ne contenait pas de JSON valide, ignoré.")
                continue
            except Exception as e:
                print(f"❌ Erreur lors du traitement du script {i+1} JSON-LD : {e}")

        print(f"📦 {len(json_products)} produits trouvés dans JSON-LD")

        # ÉTAPE 3: Associer les liens aux données JSON-LD
        for i, json_product in enumerate(json_products):
            name = json_product.get('name', 'Nom non trouvé')
            image_url = json_product.get('image', '')
            description = json_product.get('description', '')
            sku = json_product.get('sku', '')
            
            # Essayer de trouver un lien correspondant
            product_link = ""
            if i < len(product_links_data):
                # Association par index (ordre d'apparition)
                product_link = product_links_data[i]['link']
            else:
                # Fallback: construire une URL basique si possible
                if sku:
                    product_link = f"{BASE_URL}/product/{sku}"
            
            tech_specs = {"Description": description, "SKU": sku}
            datasheet_link = None

            product_data = {
                "brand": BRAND,
                "link": product_link,
                "name": name,
                "tech_specs": tech_specs,
                "scraped_at": datetime.now().isoformat(),
                "datasheet_link": datasheet_link,
                "image_url": image_url
            }
            page_products.append(product_data)
            print(f"✅ Produit assemblé: {name} -> {product_link[:50]}...")

    except TimeoutException:
        print(f"❌ Le chargement de la page de catégorie a échoué pour {category_url}")
        print("🔍 Examen de la structure de la page...")
        # Affichons le titre de la page pour diagnostiquer
        try:
            page_title = driver.title
            print(f"📋 Titre de la page : {page_title}")
            # Vérifions s'il y a des produits avec d'autres sélecteurs
            all_divs = driver.find_elements(By.TAG_NAME, "div")
            print(f"📊 {len(all_divs)} éléments div trouvés sur la page.")
        except Exception as debug_e:
            print(f"❌ Erreur de diagnostic : {debug_e}")
    except Exception as e:
        print(f"❌ Erreur majeure lors du scraping de la catégorie {category_url}: {e}")
    
    return page_products


if __name__ == "__main__":
    print(f"🚀 Démarrage du scraping pour la marque : {BRAND}")
    all_products_data = []
    
    # Boucle sur chaque URL de catégorie
    for url in URLS_TO_SCRAPE:
        products_from_category = scrape_category_page(driver, wait, url)
        all_products_data.extend(products_from_category)
        print(f"✨ {len(products_from_category)} produits ajoutés depuis cette catégorie.")
        if url != URLS_TO_SCRAPE[-1]: # Si ce n'est pas la dernière catégorie
             print(f"⏳ Pause de {DELAY_BETWEEN_PAGES} secondes avant la catégorie suivante...")
             time.sleep(DELAY_BETWEEN_PAGES)

    driver.quit()

    if all_products_data:
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(all_products_data, f, ensure_ascii=False, indent=4)
        print(f"\n🎯 Extraction terminée. {len(all_products_data)} produits au total enregistrés dans {OUTPUT_JSON}")

        if ENABLE_DB:
            print("\n💾 Tentative de sauvegarde en base de données...")
            try:
                save_to_database(OUTPUT_JSON, "serveurs", BRAND)
                print("✅ Sauvegarde en base de données réussie !")
            except Exception as e:
                print(f"❌ Erreur lors de la sauvegarde en base de données : {e}")
                print("💡 Assurez-vous que votre serveur MySQL est démarré et configuré correctement.")
        else:
            print("ℹ️ Sauvegarde BD désactivée (ENABLE_DB=false)")
    else:
        print("\n⚠️ Aucun produit n'a été extrait. Le fichier JSON n'a pas été créé.")
