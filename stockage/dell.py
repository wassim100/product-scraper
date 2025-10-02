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

# ✅ CONFIGURATION DELL STOCKAGE
BRAND = "Dell"
OUTPUT_JSON = "dell_storage_full.json"

# 📦 URLs des catégories de stockage Dell - PRODUCTION COMPLÈTE
STORAGE_URLS = [
    "https://www.dell.com/fr-fr/shop/dell-objectscale/sf/objectscale?hve=explore+objectscale",  # ObjectScale
    "https://www.dell.com/fr-fr/shop/unity-xt/sf/unity-xt?hve=explore+unity-xt",  # Unity XT
    "https://www.dell.com/fr-fr/shop/powerstore/sf/power-store?hve=explore+power-store",  # PowerStore
    "https://www.dell.com/fr-fr/shop/stockage-dell-powermax-nvme/sf/powermax?hve=explore+powermax"  # PowerMax
]

# 🔧 URLs spécifiques PowerVault - TOUS LES ONGLETS
POWERVAULT_CATEGORIES = [
    {
        "name": "PowerVault - Baies de stockage", 
        "url": "https://www.dell.com/fr-fr/shop/stockage-dell-powervault-me5/sf/powervault?hve=explore+powervault",
        "tab": "storage_arrays"
    },
    {
        "name": "PowerVault - Boîtiers d'extension", 
        "url": "https://www.dell.com/fr-fr/shop/stockage-dell-powervault-me5/sf/powervault?hve=explore+powervault",
        "tab": "expansion_enclosures"
    },
    {
        "name": "PowerVault - JBOD", 
        "url": "https://www.dell.com/fr-fr/shop/stockage-dell-powervault-me5/sf/powervault?hve=explore+powervault",
        "tab": "jbod"
    }
]

# 🔧 URLs spécifiques PowerScale - TOUS LES ONGLETS
POWERSCALE_CATEGORIES = [
    {
        "name": "PowerScale - All-Flash", 
        "url": "https://www.dell.com/fr-fr/shop/famille-powerscale/sf/powerscale?hve=explore+powerscale",
        "tab": "all_flash"
    },
    {
        "name": "PowerScale - Archive", 
        "url": "https://www.dell.com/fr-fr/shop/famille-powerscale/sf/powerscale?hve=explore+powerscale",
        "tab": "archive"
    },
    {
        "name": "PowerScale - Hybride", 
        "url": "https://www.dell.com/fr-fr/shop/famille-powerscale/sf/powerscale?hve=explore+powerscale",
        "tab": "hybride"
    }
]

# ⚙️ Configuration pour production
MAX_PRODUCTS_PER_CATEGORY = int(os.getenv("MAX_PRODUCTS", "15") or 15)
DELAY_BETWEEN_PRODUCTS = 1
DELAY_BETWEEN_CATEGORIES = 2
DELAY_FOR_PAGE_LOAD = 3

# ✅ Setup Selenium avec options anti-détection
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").strip().lower() in {"1","true","yes","on"}
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
if HEADLESS_MODE:
    options.add_argument("--headless=new")

try:
    driver = webdriver.Chrome(options=options)
except Exception:
    try:
        local_driver = os.path.join(os.getcwd(), "chromedriver.exe")
        driver = webdriver.Chrome(service=Service(local_driver), options=options)
    except Exception as e:
        raise e
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
wait = WebDriverWait(driver, 30)
driver.implicitly_wait(10)

def handle_popups_and_cookies(driver, wait):
    """Gère les popups et bannières de cookies Dell"""
    try:
        # Bannières de cookies Dell
        cookie_selectors = [
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Accepter')]", 
            "//button[contains(text(), 'I Accept')]",
            "//button[contains(text(), 'Accept All Cookies')]",
            ".onetrust-close-btn-handler",
            "#onetrust-accept-btn-handler",
            ".cookie-accept",
            ".accept-cookies",
            "[data-testid='accept-all-cookies']"
        ]
        
        for selector in cookie_selectors:
            try:
                if selector.startswith("//"):
                    cookie_btn = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                else:
                    cookie_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                print("🍪 Gestion des cookies Dell...")
                cookie_btn.click()
                time.sleep(2)
                return
            except TimeoutException:
                continue
                
        print("ℹ️ Pas de bannière de cookies détectée")
        
        # Popups génériques Dell
        popup_selectors = [
            ".modal-close",
            ".popup-close", 
            ".close-modal",
            "[aria-label='Close']",
            ".dds__modal-close"
        ]
        
        for selector in popup_selectors:
            try:
                popup_close = driver.find_element(By.CSS_SELECTOR, selector)
                if popup_close.is_displayed():
                    popup_close.click()
                    print("❌ Popup Dell fermé")
                    time.sleep(1)
            except:
                continue
                
    except Exception as e:
        print(f"⚠️ Erreur gestion popups Dell: {e}")

def click_dell_tab(driver, wait, tab_name):
    """Clique sur l'onglet Dell spécifié (PowerVault ou PowerScale)"""
    try:
        # Si c'est "storage_arrays" ou "all_flash", c'est déjà ouvert par défaut
        if tab_name in ["storage_arrays", "all_flash"]:
            print(f"📑 Onglet '{tab_name}' déjà ouvert par défaut")
            return True
        
        print(f"🔍 Recherche de l'onglet Dell: {tab_name}")
        
        # Sélecteurs précis basés sur l'analyse du HTML Dell
        tab_selectors = {
            # PowerVault onglets
            "expansion_enclosures": [
                "button[id*='Boitiers']",              # ID sans apostrophe
                "button[aria-controls*='Boitiers']",   # Aria controls sans apostrophe
                "//button[contains(text(), 'Boîtiers')]",  # Texte avec apostrophe (XPath)
                "//button[contains(@id, 'Boitiers')]",     # ID avec XPath
                ".dds__accordion__button:nth-child(2)",    # 2ème bouton d'accordéon
                ".dds__accordion__item:nth-child(2) button" # Bouton dans 2ème item
            ],
            "jbod": [
                "button[id='cmfe-trigger-JBOD']",      # ID exact
                "button[aria-controls='cmfe-content-JBOD']",  # Aria controls exact
                "//button[contains(text(), 'JBOD')]",  # Texte exact (XPath)
                "//button[contains(@id, 'JBOD')]",     # ID avec XPath
                ".dds__accordion__button:nth-child(3)",    # 3ème bouton d'accordéon  
                ".dds__accordion__item:nth-child(3) button" # Bouton dans 3ème item
            ],
            # PowerScale onglets
            "archive": [
                "button[id='cmfe-trigger-Archive']",   # ID exact
                "button[aria-controls='cmfe-content-Archive']",  # Aria controls exact
                "//button[contains(text(), 'Archive')]",  # Texte exact (XPath)
                "//button[contains(@id, 'Archive')]",     # ID avec XPath
                ".dds__accordion__button:nth-child(2)",    # 2ème bouton d'accordéon
                ".dds__accordion__item:nth-child(2) button" # Bouton dans 2ème item
            ],
            "hybride": [
                "button[id='cmfe-trigger-Hybride']",   # ID exact
                "button[aria-controls='cmfe-content-Hybride']",  # Aria controls exact
                "//button[contains(text(), 'Hybride')]",  # Texte exact (XPath)
                "//button[contains(@id, 'Hybride')]",     # ID avec XPath
                ".dds__accordion__button:nth-child(3)",    # 3ème bouton d'accordéon  
                ".dds__accordion__item:nth-child(3) button" # Bouton dans 3ème item
            ]
        }
        
        if tab_name not in tab_selectors:
            print(f"⚠️ Tab '{tab_name}' non reconnu")
            return True
        
        # Essayer chaque sélecteur pour l'onglet demandé
        for i, selector in enumerate(tab_selectors[tab_name], 1):
            try:
                print(f"   🔍 Tentative {i}: {selector}")
                
                if selector.startswith("//"):
                    # XPath selector
                    elements = driver.find_elements(By.XPATH, selector)
                    if elements:
                        element = elements[0]
                        print(f"   ✅ Onglet trouvé avec XPath: {selector}")
                        
                        # Scroll vers l'élément et cliquer avec JavaScript
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", element)
                        print(f"   📑 Clic sur l'onglet Dell '{tab_name}' réussi avec JS")
                        time.sleep(3)
                        return True
                else:
                    # CSS selector
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        element = elements[0]
                        if element.is_displayed():
                            print(f"   ✅ Onglet trouvé avec CSS: {selector}")
                            
                            # Scroll vers l'élément et cliquer
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                            time.sleep(1)
                            
                            try:
                                element.click()
                            except:
                                # Fallback avec JavaScript
                                driver.execute_script("arguments[0].click();", element)
                            
                            print(f"   📑 Clic sur l'onglet Dell '{tab_name}' réussi")
                            time.sleep(3)
                            return True
                        else:
                            print(f"   ⚠️ Élément trouvé mais non visible: {selector}")
                    
            except Exception as e:
                print(f"   ❌ Erreur avec {selector}: {str(e)[:100]}...")
                continue
        
        print(f"⚠️ Onglet Dell '{tab_name}' non trouvé - continuons avec l'onglet par défaut")
        return True  # Continue quand même
        
    except Exception as e:
        print(f"❌ Erreur clic onglet Dell {tab_name}: {e}")
        return True

def extract_products_from_category_page(driver, wait, category_url, tab_info=None):
    """Extrait tous les produits d'une page de catégorie Dell"""
    products = []
    
    try:
        print(f"🌐 Accès à la catégorie Dell: {category_url}")
        driver.get(category_url)
        
        # Gérer les popups
        handle_popups_and_cookies(driver, wait)
        
        # Si c'est PowerVault ou PowerScale avec des onglets, cliquer sur l'onglet spécifique
        if tab_info:
            print(f"🔄 Basculement vers l'onglet: {tab_info['name']}")
            success = click_dell_tab(driver, wait, tab_info['tab'])
            if success and tab_info['tab'] not in ["storage_arrays", "all_flash"]:
                # Attendre que le contenu de l'onglet soit chargé
                try:
                    # Attendre que les lignes cachées deviennent visibles
                    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, 
                        "div[role='row'].cmfe-row:not(.cmfe-header-row):not(.dds__d-none)")) > 0)
                    time.sleep(2)  # Délai supplémentaire pour stabilisation
                except TimeoutException:
                    print("⚠️ Timeout en attendant le chargement du contenu de l'onglet")
        
        # Attendre le chargement du tableau Dell
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.cmfe-table")))
            time.sleep(DELAY_FOR_PAGE_LOAD)
        except TimeoutException:
            print(f"⚠️ Tableau Dell non trouvé, essai avec sélecteur alternatif...")
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[role='table']")))
                time.sleep(DELAY_FOR_PAGE_LOAD)
            except TimeoutException:
                print(f"❌ Aucun tableau de produits trouvé sur {category_url}")
                return products
        
        # Trouver toutes les lignes de produits Dell selon l'onglet actif
        if tab_info and tab_info['tab'] not in ["storage_arrays", "all_flash"]:
            # Pour les onglets non-défaut, chercher les lignes sans "dds__d-none" (visibles)
            product_rows = driver.find_elements(By.CSS_SELECTOR, "div[role='row'].cmfe-row:not(.cmfe-header-row):not(.dds__d-none)")
        else:
            # Pour l'onglet par défaut, chercher toutes les lignes sauf celles marquées cachées
            product_rows = driver.find_elements(By.CSS_SELECTOR, "div[role='row'].cmfe-row:not(.cmfe-header-row)")
            # Filtrer les lignes cachées (avec dds__d-none)
            visible_rows = []
            for row in product_rows:
                if "dds__d-none" not in row.get_attribute("class"):
                    visible_rows.append(row)
            product_rows = visible_rows
        
        # Filtrer les lignes de données (exclure les headers ET les lignes vides)
        valid_rows = []
        for row in product_rows:
            # Vérifier qu'il y a du contenu dans la ligne
            try:
                # Chercher un nom de produit pour valider la ligne
                name_element = row.find_element(By.CSS_SELECTOR, ".cmfe-variant-title")
                if name_element.text.strip():
                    valid_rows.append(row)
            except:
                # Si pas de nom, ignorer cette ligne
                continue
        
        product_rows = valid_rows
        
        if not product_rows:
            print(f"❌ Aucun produit trouvé sur {category_url}")
            return products
            
        print(f"📦 {len(product_rows)} produits Dell trouvés sur cette catégorie")
        
        # Limiter pour la production
        product_rows = product_rows[:MAX_PRODUCTS_PER_CATEGORY]
        print(f"🔬 Traitement de {len(product_rows)} produits maximum")
        
        for index, row in enumerate(product_rows):
            try:
                # Extraire les informations du produit Dell
                product_info = extract_dell_product_info(row, index + 1, len(product_rows), category_url)
                
                if not product_info:
                    continue
                    
                # Combiner les informations
                category_name = tab_info['name'] if tab_info else extract_category_from_url(category_url)
                product_data = {
                    "brand": BRAND,
                    "category": category_name,
                    "link": product_info.get("link", ""),
                    "name": product_info["name"],
                    "tech_specs": product_info["tech_specs"],
                    "scraped_at": datetime.now().isoformat(),
                    "datasheet_link": product_info.get("datasheet_link", None),
                    "image_url": product_info.get("image_url", "")
                }
                
                products.append(product_data)
                print(f"✅ [{index+1}/{len(product_rows)}] {product_info['name']} - {len(product_info['tech_specs'])} spécifications")
                
                # Pause entre produits
                time.sleep(DELAY_BETWEEN_PRODUCTS)
                
            except Exception as e:
                print(f"❌ Erreur produit Dell {index+1}: {e}")
                continue
                
    except Exception as e:
        print(f"❌ Erreur catégorie Dell {category_url}: {e}")
        
    return products

def extract_dell_product_info(product_row, current, total, category_url):
    """Extrait les informations d'un produit Dell depuis sa ligne de tableau"""
    try:
        # Nom du produit Dell
        name_element = None
        name_selectors = [
            ".cmfe-variant-title",
            "strong.dds__subtitle-2",
            ".cmfe-model strong",
            "[data-testid*='product-name']",
            ".product-title",
            "h3", "h4", "h5",  # Headers génériques
            "strong", "b"      # Texte en gras
        ]
        
        print(f"🔍 [{current}/{total}] Recherche du nom produit...")
        
        for i, selector in enumerate(name_selectors):
            try:
                elements = product_row.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.strip()
                    if text and len(text) > 5:  # Nom raisonnable
                        name_element = element
                        print(f"   ✅ Nom trouvé: {text}")
                        break
                if name_element:
                    break
            except Exception as e:
                continue
                
        if not name_element:
            print(f"⚠️ [{current}/{total}] Nom produit Dell non trouvé")
            return None
            
        name = name_element.text.strip()
        
        # Image du produit Dell
        image_url = ""
        try:
            img_element = product_row.find_element(By.CSS_SELECTOR, ".cmfe-variant-image")
            image_url = img_element.get_attribute("src")
            if image_url and not image_url.startswith("http"):
                image_url = "https:" + image_url
        except:
            pass
        
        # Lien vers la fiche technique Dell
        datasheet_link = ""
        try:
            spec_link = product_row.find_element(By.CSS_SELECTOR, "a.cmfe-spec-link")
            datasheet_link = spec_link.get_attribute("href")
        except:
            pass
        
        # Extraire les spécifications depuis les cellules du tableau Dell
        tech_specs = {}
        spec_cells = product_row.find_elements(By.CSS_SELECTOR, "div[role='cell'].cmfe-col-inner")
        
        # Mapping des colonnes Dell selon l'analyse HTML
        spec_mapping = {
            0: "Meilleure utilisation",
            1: "Stockage", 
            2: "Capacité de nœuds brute",
            3: "Nœuds par rack",
            4: "Capacité brute du rack",
            5: "Disque SSD de cache"
        }
        
        for i, cell in enumerate(spec_cells):
            if i in spec_mapping:
                try:
                    value = cell.text.strip()
                    if value:
                        tech_specs[spec_mapping[i]] = value
                except Exception as e:
                    continue
        
        if not name:
            print(f"⚠️ [{current}/{total}] Produit Dell incomplet ignoré")
            return None
            
        print(f"📋 [{current}/{total}] Produit Dell détecté: {name}")
        
        return {
            "name": name,
            "tech_specs": tech_specs,
            "datasheet_link": datasheet_link,
            "image_url": image_url,
            "link": datasheet_link  # Pour Dell, le lien principal est la fiche technique
        }
        
    except Exception as e:
        print(f"❌ Erreur extraction info Dell: {e}")
        return None

def extract_category_from_url(url):
    """Extrait le nom de la catégorie depuis l'URL Dell"""
    category_mapping = {
        "objectscale": "ObjectScale - Stockage Objet",
        "unity-xt": "Unity XT - Stockage Hybride",
        "powervault": "PowerVault - Stockage d'Entrée de Gamme",
        "powerscale": "PowerScale - Stockage Scale-Out",
        "power-store": "PowerStore - All-Flash",
        "powermax": "PowerMax - Stockage Stratégique"
    }
    
    for key, category in category_mapping.items():
        if key in url:
            return category
            
    return "Dell Storage Solutions"

def scrape_all_dell_storage():
    """Fonction principale pour scraper tout le stockage Dell"""
    print("🚀 Dell Storage - Toutes catégories (ObjectScale + Unity XT + PowerStore + PowerMax + PowerVault + PowerScale)")
    all_products = []
    
    # Configuration du driver WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        driver = webdriver.Chrome(options=options)
    except Exception:
        try:
            local_driver = os.path.join(os.getcwd(), "chromedriver.exe")
            driver = webdriver.Chrome(service=Service(local_driver), options=options)
        except Exception as e:
            raise e
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    wait = WebDriverWait(driver, 15)
    
    try:
        # 1. Scraper ObjectScale, Unity XT, PowerStore et PowerMax
        for i, category_url in enumerate(STORAGE_URLS, 1):
            try:
                print(f"\n📂 [{i}/{len(STORAGE_URLS) + len(POWERVAULT_CATEGORIES) + len(POWERSCALE_CATEGORIES)}] Traitement catégorie Dell: {extract_category_from_url(category_url)}")
                
                # Extraire les produits de cette catégorie Dell
                category_products = extract_products_from_category_page(driver, wait, category_url)
                all_products.extend(category_products)
                
                print(f"✅ Catégorie Dell {i} terminée - {len(category_products)} produits extraits")
                
                # Pause entre catégories
                print(f"⏳ Pause de {DELAY_BETWEEN_CATEGORIES}s entre catégories Dell...")
                time.sleep(DELAY_BETWEEN_CATEGORIES)
                    
            except Exception as e:
                print(f"❌ Erreur catégorie Dell {i}: {e}")
                continue
        
        # 2. Scraper PowerVault (tous les onglets)
        base_index = len(STORAGE_URLS)
        for i, powervault_tab in enumerate(POWERVAULT_CATEGORIES, base_index + 1):
            try:
                print(f"\n📂 [{i}/{len(STORAGE_URLS) + len(POWERVAULT_CATEGORIES) + len(POWERSCALE_CATEGORIES)}] PowerVault: {powervault_tab['name']}")
                
                # Extraire les produits de cet onglet PowerVault
                category_products = extract_products_from_category_page(
                    driver, wait, powervault_tab['url'], powervault_tab
                )
                all_products.extend(category_products)
                
                print(f"✅ PowerVault onglet {i-base_index} terminé - {len(category_products)} produits extraits")
                
                # Pause entre onglets PowerVault
                if i < base_index + len(POWERVAULT_CATEGORIES):
                    print(f"⏳ Pause de {DELAY_BETWEEN_CATEGORIES}s entre onglets PowerVault...")
                    time.sleep(DELAY_BETWEEN_CATEGORIES)
                    
            except Exception as e:
                print(f"❌ Erreur onglet PowerVault {i}: {e}")
                continue
                
        # 3. Scraper PowerScale (tous les onglets)
        base_index_2 = len(STORAGE_URLS) + len(POWERVAULT_CATEGORIES)
        for i, powerscale_tab in enumerate(POWERSCALE_CATEGORIES, base_index_2 + 1):
            try:
                print(f"\n📂 [{i}/{len(STORAGE_URLS) + len(POWERVAULT_CATEGORIES) + len(POWERSCALE_CATEGORIES)}] PowerScale: {powerscale_tab['name']}")
                
                # Extraire les produits de cet onglet PowerScale
                category_products = extract_products_from_category_page(
                    driver, wait, powerscale_tab['url'], powerscale_tab
                )
                all_products.extend(category_products)
                
                print(f"✅ PowerScale onglet {i-base_index_2} terminé - {len(category_products)} produits extraits")
                
                # Pause entre onglets PowerScale
                if i < base_index_2 + len(POWERSCALE_CATEGORIES):
                    print(f"⏳ Pause de {DELAY_BETWEEN_CATEGORIES}s entre onglets PowerScale...")
                    time.sleep(DELAY_BETWEEN_CATEGORIES)
                    
            except Exception as e:
                print(f"❌ Erreur onglet PowerScale {i}: {e}")
                continue
        
        # Supprimer les doublons basés sur le nom
        unique_products = []
        seen_names = set()
        
        for product in all_products:
            if product['name'] not in seen_names:
                unique_products.append(product)
                seen_names.add(product['name'])
        
        print(f"\n🎯 Dell Storage terminé!")
        print(f"📊 {len(all_products)} produits Dell trouvés au total")
        print(f"🔗 {len(unique_products)} produits Dell uniques après déduplication")
        
        return unique_products
        
    finally:
        # Fermer le driver dans tous les cas
        driver.quit()
        print("🔒 Driver WebDriver fermé")

if __name__ == "__main__":
    try:
        products = scrape_all_dell_storage()
        
        if products:
            # Sauvegarder en JSON
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=4)
            print(f"💾 Données Dell sauvegardées dans {OUTPUT_JSON}")
            
            # Sauvegarde en base de données conditionnelle
            if ENABLE_DB:
                try:
                    save_to_database(OUTPUT_JSON, "stockage", BRAND)
                    print("✅ Sauvegarde Dell en base de données réussie!")
                except Exception as e:
                    print(f"❌ Erreur sauvegarde base de données Dell: {e}")
                    print("💡 Assurez-vous que MySQL est installé et configuré")
            else:
                print("ℹ️ Sauvegarde BD désactivée (ENABLE_DB=false)")
        else:
            print("⚠️ Aucun produit Dell n'a été extrait.")
            
    except Exception as e:
        print(f"❌ Erreur fatale Dell: {e}")
    finally:
        driver.quit()
