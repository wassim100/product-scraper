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

# --- CONFIGURATION DELL ---
BASE_URL = "https://www.dell.com/fr-fr/shop/serveurs-ia-poweredge/sf/poweredge-ai-servers?hve=explore+poweredge-ai-servers"
BRAND = "Dell"
OUTPUT_JSON = "dell_servers_full.json"
CHROMEDRIVER_PATH = os.path.join(os.getcwd(), "chromedriver.exe")

# --- CONFIGURATION POUR LE TEST ---
DELAY_BETWEEN_TABS = 3
DELAY_BETWEEN_SOCKETS = 2
DELAY_BETWEEN_PRODUCTS = 1

# --- SETUP SELENIUM ---
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# from database.mysql_connector import save_to_database  # Désactivé temporairement pour les tests

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

# --- FONCTIONS DE SCRAPING DELL ---

def handle_cookie_banner(driver, wait):
    """Gère les bannières de cookies Dell."""
    try:
        # Dell utilise souvent des boutons "Accept" ou "I Accept"
        cookie_selectors = [
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'I Accept')]",
            "//button[contains(text(), 'Accepter')]",
            "#onetrust-accept-btn-handler"
        ]
        
        for selector in cookie_selectors:
            try:
                if selector.startswith("//"):
                    cookie_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                else:
                    cookie_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                print(f"🍪 Bannière de cookies trouvée. Clic sur le bouton.")
                cookie_button.click()
                time.sleep(2)
                return
            except TimeoutException:
                continue
                
        print("ℹ️ Pas de bannière de cookies trouvée ou déjà acceptée.")
    except Exception as e:
        print(f"⚠️ Erreur lors de la gestion des cookies : {e}")

def get_available_tabs(driver):
    """Récupère tous les onglets disponibles (Serveurs IA, Serveurs rack, etc.)."""
    tabs = []
    try:
        # Chercher les onglets dans la liste des tabs
        tab_elements = driver.find_elements(By.CSS_SELECTOR, ".dds_tabs_list li[role='none']")
        
        for tab in tab_elements:
            try:
                # Chercher le bouton ou lien dans l'onglet
                clickable = tab.find_element(By.CSS_SELECTOR, "button, a")
                tab_text = clickable.text.strip()
                if tab_text and tab_text not in ['', ' ']:
                    tabs.append({
                        'name': tab_text,
                        'element': clickable
                    })
            except:
                continue
                
        print(f"📂 {len(tabs)} onglets trouvés : {[tab['name'] for tab in tabs]}")
        return tabs
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des onglets : {e}")
        return []

def get_available_sockets(driver):
    """Récupère les options de socket disponibles (1, 2, 4 sockets)."""
    sockets = []
    try:
        # Chercher les options de socket (probablement des boutons radio ou des liens)
        socket_selectors = [
            "//button[contains(text(), 'socket')]",
            "//a[contains(text(), 'socket')]",
            "//label[contains(text(), 'socket')]",
            ".socket-option",
            "[data-socket]"
        ]
        
        for selector in socket_selectors:
            try:
                if selector.startswith("//"):
                    socket_elements = driver.find_elements(By.XPATH, selector)
                else:
                    socket_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in socket_elements:
                    text = element.text.strip()
                    if 'socket' in text.lower() and text not in [s['name'] for s in sockets]:
                        sockets.append({
                            'name': text,
                            'element': element
                        })
            except:
                continue
                
        # Si pas trouvé, chercher les attributs data-socket dans les produits
        if not sockets:
            products = driver.find_elements(By.CSS_SELECTOR, "[data-socket]")
            socket_values = set()
            for product in products:
                socket_val = product.get_attribute("data-socket")
                if socket_val:
                    socket_values.add(socket_val)
            
            # Créer des entrées fictives pour les valeurs trouvées
            for socket_val in sorted(socket_values):
                sockets.append({
                    'name': f"{socket_val} socket{'s' if socket_val != '1' else ''}",
                    'value': socket_val
                })
                
        print(f"🔌 {len(sockets)} options de socket trouvées : {[s['name'] for s in sockets]}")
        return sockets
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des options de socket : {e}")
        return []

def extract_products_from_current_page(driver):
    """Extrait tous les produits visibles sur la page actuelle."""
    products = []
    
    try:
        # Attendre que les produits soient chargés
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cmfe-row[data-ff-id]")))
        time.sleep(2)  # Laisser le temps au JavaScript de finir
        
        # Trouver tous les conteneurs de produits
        product_containers = driver.find_elements(By.CSS_SELECTOR, ".cmfe-row[data-ff-id]")
        print(f"📦 {len(product_containers)} conteneurs de produits trouvés")
        
        for container in product_containers:
            try:
                # Extraire le nom du produit avec plusieurs sélecteurs
                name = ""
                name_selectors = [
                    ".cmfe-variant-title",
                    ".dds__subtitle-2", 
                    "strong.cmfe-variant-title",
                    "strong.dds__subtitle-2",
                    ".product-title",
                    "h3", "h4", "h5"
                ]
                
                for selector in name_selectors:
                    try:
                        name_element = container.find_element(By.CSS_SELECTOR, selector)
                        name = name_element.text.strip()
                        if name:
                            break
                    except:
                        continue
                
                # Si toujours pas de nom, essayer depuis l'attribut aria-label du lien
                if not name:
                    try:
                        link_element = container.find_element(By.CSS_SELECTOR, ".cmfe-shop-link")
                        aria_label = link_element.get_attribute("aria-label")
                        if aria_label and "Acheter dès maintenant" in aria_label:
                            name = aria_label.replace("Acheter dès maintenant des ", "").replace("Acheter dès maintenant de ", "")
                    except:
                        pass
                
                # Extraire le lien du produit
                link_element = container.find_element(By.CSS_SELECTOR, ".cmfe-shop-link")
                link = link_element.get_attribute("href")
                
                # Extraire l'image
                image_element = container.find_element(By.CSS_SELECTOR, ".cmfe-variant-image")
                image_url = image_element.get_attribute("src") or image_element.get_attribute("data-src")
                
                # Extraire le lien vers la datasheet
                datasheet_link = None
                try:
                    datasheet_element = container.find_element(By.CSS_SELECTOR, ".cmfe-spec-link")
                    datasheet_link = datasheet_element.get_attribute("href")
                except:
                    pass
                
                # Extraire les spécifications depuis les cellules
                cells = container.find_elements(By.CSS_SELECTOR, ".cmfe-col-inner")
                tech_specs = {
                    "Description": []
                }
                
                # Mapper les cellules aux spécifications
                spec_labels = [
                    "Charges applicatives",
                    "Unités de rack", 
                    "Processeur",
                    "Mémoire max",
                    "Espace de stockage max",
                    "Processeur graphique"
                ]
                
                for i, cell in enumerate(cells):
                    if i < len(spec_labels):
                        spec_value = cell.text.strip()
                        if spec_value:
                            tech_specs[spec_labels[i]] = spec_value
                
                # Récupérer l'attribut data-socket
                socket_info = container.get_attribute("data-socket")
                if socket_info:
                    tech_specs["Socket"] = f"{socket_info} socket{'s' if socket_info != '1' else ''}"
                
                # Ne pas ajouter les produits sans nom
                if not name:
                    print(f"⚠️ Produit sans nom ignoré : {link}")
                    continue
                
                # Créer l'objet produit
                product_data = {
                    "brand": BRAND,
                    "link": link,
                    "name": name,
                    "tech_specs": tech_specs,
                    "scraped_at": datetime.now().isoformat(),
                    "datasheet_link": datasheet_link,
                    "image_url": [image_url] if image_url else []
                }
                
                products.append(product_data)
                print(f"✅ Produit extrait : {name}")
                
            except Exception as e:
                print(f"⚠️ Erreur lors de l'extraction d'un produit : {e}")
                continue
                
    except TimeoutException:
        print("❌ Timeout lors de l'attente des produits")
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction des produits : {e}")
    
    return products

def scrape_dell_servers():
    """Fonction principale pour scraper tous les serveurs Dell."""
    print(f"🚀 Démarrage du scraping Dell - {BRAND}")
    all_products = []
    
    # Aller sur la page principale
    print(f"🌐 Accès à la page : {BASE_URL}")
    driver.get(BASE_URL)
    
    # Gérer les cookies
    handle_cookie_banner(driver, wait)
    
    # Attendre que la page soit chargée
    time.sleep(5)
    
    # Récupérer les onglets disponibles
    tabs = get_available_tabs(driver)
    
    if not tabs:
        print("⚠️ Aucun onglet trouvé, tentative d'extraction directe...")
        products = extract_products_from_current_page(driver)
        all_products.extend(products)
    else:
        # Parcourir chaque onglet
        for tab in tabs:
            print(f"\n📂 Traitement de l'onglet : {tab['name']}")
            
            try:
                # Cliquer sur l'onglet
                driver.execute_script("arguments[0].click();", tab['element'])
                time.sleep(DELAY_BETWEEN_TABS)
                
                # Récupérer les options de socket pour cet onglet
                sockets = get_available_sockets(driver)
                
                if not sockets:
                    # Pas d'options de socket, extraire directement
                    products = extract_products_from_current_page(driver)
                    all_products.extend(products)
                else:
                    # Parcourir chaque option de socket
                    for socket_option in sockets:
                        print(f"🔌 Option socket : {socket_option['name']}")
                        
                        try:
                            # Si c'est un élément cliquable
                            if 'element' in socket_option:
                                driver.execute_script("arguments[0].click();", socket_option['element'])
                                time.sleep(DELAY_BETWEEN_SOCKETS)
                            
                            # Extraire les produits pour cette combinaison onglet/socket
                            products = extract_products_from_current_page(driver)
                            all_products.extend(products)
                            
                        except Exception as e:
                            print(f"❌ Erreur lors du traitement de l'option socket {socket_option['name']} : {e}")
                            continue
                            
            except Exception as e:
                print(f"❌ Erreur lors du traitement de l'onglet {tab['name']} : {e}")
                continue
    
    # Supprimer les doublons basés sur le lien
    unique_products = []
    seen_links = set()
    
    for product in all_products:
        if product['link'] not in seen_links:
            unique_products.append(product)
            seen_links.add(product['link'])
    
    print(f"\n🎯 Extraction terminée !")
    print(f"📊 {len(all_products)} produits trouvés au total")
    print(f"🔗 {len(unique_products)} produits uniques après déduplication")
    
    return unique_products

if __name__ == "__main__":
    try:
        products = scrape_dell_servers()
        
        if products:
            # Sauvegarder en JSON
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=4)
            print(f"💾 Données sauvegardées dans {OUTPUT_JSON}")
            
            # Sauvegarde en base de données (désactivée pour les tests)
            # try:
            #     save_to_database(OUTPUT_JSON, "serveurs", BRAND)
            #     print("✅ Sauvegarde en base de données réussie !")
            # except Exception as e:
            #     print(f"❌ Erreur lors de la sauvegarde en base de données : {e}")
            print("💾 Sauvegarde en base de données désactivée pour les tests.")
        else:
            print("⚠️ Aucun produit n'a été extrait.")
            
    except Exception as e:
        print(f"❌ Erreur fatale : {e}")
    finally:
        driver.quit()
