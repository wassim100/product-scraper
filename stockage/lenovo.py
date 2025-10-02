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

# ✅ CONFIGURATION LENOVO STOCKAGE
BRAND = "Lenovo"
OUTPUT_JSON = "lenovo_storage_full.json"

# 📦 URLs des catégories de stockage Lenovo - PRODUCTION COMPLÈTE
STORAGE_URLS = [
    "https://www.lenovo.com/tn/fr/c/servers-storage/storage/unified-storage/dg-series-all-flash/",  # DG Series All-Flash
    "https://www.lenovo.com/tn/fr/c/servers-storage/storage/unified-storage/dm-series-all-flash/",  # DM Series All-Flash
    "https://www.lenovo.com/tn/fr/c/servers-storage/storage/unified-storage/dm-series-hybrid-flash/",  # DM Series Hybrid
    "https://www.lenovo.com/tn/fr/c/servers-storage/storage/storage-area-network/de-hybrid-flash-array/",  # DE Hybrid Flash
    "https://www.lenovo.com/tn/fr/c/servers-storage/storage/das/",  # Direct Attached Storage
    "https://www.lenovo.com/tn/fr/c/servers-storage/storage/storage-area-network/san-fibre-channel-switches/"  # SAN Switches
]

# ⚙️ Configuration pour production complète
MAX_PRODUCTS_PER_CATEGORY = int(os.getenv("MAX_PRODUCTS", "15") or 15)
DELAY_BETWEEN_PRODUCTS = 1
DELAY_BETWEEN_CATEGORIES = 1
DELAY_FOR_PAGE_LOAD = 2

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
    """Gère les popups et bannières de cookies Lenovo"""
    try:
        # Bannières de cookies Lenovo
        cookie_selectors = [
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Accepter')]", 
            "//button[contains(text(), 'I Accept')]",
            ".onetrust-close-btn-handler",
            "#onetrust-accept-btn-handler",
            ".cookie-accept",
            ".accept-cookies"
        ]
        
        for selector in cookie_selectors:
            try:
                if selector.startswith("//"):
                    cookie_btn = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                else:
                    cookie_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                print("🍪 Gestion des cookies...")
                cookie_btn.click()
                time.sleep(2)
                return
            except TimeoutException:
                continue
                
        print("ℹ️ Pas de bannière de cookies détectée")
        
        # Popups génériques
        popup_selectors = [
            ".modal-close",
            ".popup-close", 
            ".close-modal",
            "[aria-label='Close']"
        ]
        
        for selector in popup_selectors:
            try:
                popup_close = driver.find_element(By.CSS_SELECTOR, selector)
                if popup_close.is_displayed():
                    popup_close.click()
                    print("❌ Popup fermé")
                    time.sleep(1)
            except:
                continue
                
    except Exception as e:
        print(f"⚠️ Erreur gestion popups: {e}")

def extract_products_from_category_page(driver, wait, category_url):
    """Extrait tous les produits d'une page de catégorie"""
    products = []
    
    try:
        print(f"🌐 Accès à la catégorie: {category_url}")
        driver.get(category_url)
        
        # Gérer les popups
        handle_popups_and_cookies(driver, wait)
        
        # Attendre le chargement des produits
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.skeleton_product")))
        time.sleep(DELAY_FOR_PAGE_LOAD)
        
        # Trouver tous les produits
        product_items = driver.find_elements(By.CSS_SELECTOR, "ul.skeleton_product li.product_item")
        
        if not product_items:
            print(f"❌ Aucun produit trouvé sur {category_url}")
            return products
            
        print(f"📦 {len(product_items)} produits trouvés sur cette catégorie")
        
        # Limiter pour les tests
        product_items = product_items[:MAX_PRODUCTS_PER_CATEGORY]
        print(f"🔬 Test avec {len(product_items)} produits maximum")
        
        for index, item in enumerate(product_items):
            try:
                # Extraire les informations de base
                product_info = extract_basic_product_info(item, index + 1, len(product_items))
                
                if not product_info:
                    continue
                    
                # IMPORTANT: Cliquer sur "Learn More" depuis la liste pour accéder aux spécifications
                detailed_specs = click_learn_more_and_extract_specs(driver, wait, item, product_info["name"])
                
                # Combiner les informations
                product_data = {
                    "brand": BRAND,
                    "category": extract_category_from_url(category_url),
                    "link": product_info["link"],
                    "name": product_info["name"],
                    "tech_specs": detailed_specs,
                    "scraped_at": datetime.now().isoformat(),
                    "datasheet_link": None,  # Pas de datasheet selon vos infos
                    "image_url": product_info["image_url"]
                }
                
                products.append(product_data)
                print(f"✅ [{index+1}/{len(product_items)}] {product_info['name']} - {len(detailed_specs)} spécifications")
                
                # Pause entre produits
                time.sleep(DELAY_BETWEEN_PRODUCTS)
                
            except Exception as e:
                print(f"❌ Erreur produit {index+1}: {e}")
                continue
                
    except Exception as e:
        print(f"❌ Erreur catégorie {category_url}: {e}")
        
    return products

def extract_basic_product_info(product_item, current, total):
    """Extrait les informations de base d'un produit depuis la liste"""
    try:
        # Nom du produit
        name_element = product_item.find_element(By.CSS_SELECTOR, ".product_title a")
        name = name_element.text.strip()
        
        # Lien du produit
        link = name_element.get_attribute("href")
        
        # Assurer que le lien est complet
        if not link.startswith("http"):
            link = "https://www.lenovo.com" + link
            
        # Image du produit
        image_url = ""
        try:
            img_element = product_item.find_element(By.CSS_SELECTOR, ".card_product_image img.image_focus")
            image_url = img_element.get_attribute("src")
            if image_url and not image_url.startswith("http"):
                image_url = "https:" + image_url
        except:
            pass
            
        if not name or not link:
            print(f"⚠️ [{current}/{total}] Produit incomplet ignoré")
            return None
            
        print(f"📋 [{current}/{total}] Produit détecté: {name}")
        
        return {
            "name": name,
            "link": link, 
            "image_url": image_url
        }
        
    except Exception as e:
        print(f"❌ Erreur extraction info de base: {e}")
        return None

def click_learn_more_and_extract_specs(driver, wait, product_item, product_name):
    """Clique sur 'Learn More' depuis la liste et extrait les spécifications techniques"""
    detailed_specs = {}
    original_window = driver.current_window_handle
    
    try:
        print(f"🔍 Recherche bouton 'Learn More' pour: {product_name}")
        
        # Chercher le bouton "Learn More" dans l'item produit
        learn_more_selectors = [
            ".cta-button.indirect-button",
            ".cta-button",
            ".learn-more",
            "//a[contains(text(), 'Learn More')]",
            "//a[contains(text(), 'En savoir plus')]"
        ]
        
        learn_more_clicked = False
        for selector in learn_more_selectors:
            try:
                if selector.startswith("//"):
                    learn_more_btn = product_item.find_element(By.XPATH, selector)
                else:
                    learn_more_btn = product_item.find_element(By.CSS_SELECTOR, selector)
                    
                if learn_more_btn.is_displayed():
                    # Scroll vers le bouton
                    driver.execute_script("arguments[0].scrollIntoView(true);", learn_more_btn)
                    time.sleep(1)
                    
                    # Obtenir le lien avant de cliquer
                    product_link = learn_more_btn.get_attribute("href")
                    
                    # Ouvrir dans un nouvel onglet
                    driver.execute_script("window.open(arguments[0]);", product_link)
                    driver.switch_to.window(driver.window_handles[1])
                    
                    print(f"✅ Ouverture page produit via 'Learn More': {product_name}")
                    learn_more_clicked = True
                    break
                    
            except:
                continue
                
        if not learn_more_clicked:
            print(f"⚠️ Bouton 'Learn More' non trouvé pour {product_name}")
            return detailed_specs
        
        # Attendre le chargement de la page
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(DELAY_FOR_PAGE_LOAD)
        
        # Chercher et cliquer sur l'onglet Tech Specs
        print(f"📊 Recherche onglet Tech Specs pour: {product_name}")
        tech_specs_clicked = False
        
        tech_specs_selectors = [
            "section[name='tech_specs'] .title",
            ".tech_specs_container .title", 
            "//div[contains(text(), 'Tech Specs')]",
            "//button[contains(text(), 'Tech Specs')]",
            "//a[contains(text(), 'Tech Specs')]",
            "[data-tkey='haloSubseriesTechSpecs']",
            "//button[contains(text(), 'Spécifications')]",
            "//a[contains(text(), 'Spécifications')]"
        ]
        
        for selector in tech_specs_selectors:
            try:
                if selector.startswith("//"):
                    tech_specs_btn = driver.find_element(By.XPATH, selector)
                else:
                    tech_specs_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    
                if tech_specs_btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView(true);", tech_specs_btn)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", tech_specs_btn)
                    print("📊 Onglet Tech Specs activé")
                    tech_specs_clicked = True
                    time.sleep(3)  # Attendre le chargement des spécifications
                    break
            except:
                continue
                
        if not tech_specs_clicked:
            print(f"⚠️ Onglet Tech Specs non trouvé pour {product_name}")
        
        # Extraire les spécifications depuis le tableau
        try:
            # Attendre que le contenu des specs soit visible
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".specs-table, .tech_specs_inner")))
            
            # Méthode 1: Tableau structuré (format identique au scraper serveurs)
            spec_items = driver.find_elements(By.CSS_SELECTOR, ".specs-table .item")
            print(f"🔍 Trouvé {len(spec_items)} items de spécifications")
            
            for item in spec_items:
                try:
                    # Debug: Afficher la structure HTML de l'item
                    item_html = item.get_attribute("outerHTML")
                    print(f"🔍 Structure HTML item: {item_html[:200]}...")
                    
                    # Extraire la clé (titre de la spécification) - utiliser innerHTML au lieu de text
                    key_element = item.find_element(By.CSS_SELECTOR, ".spec-title")
                    key = key_element.get_attribute("innerHTML").strip()
                    # Nettoyer le HTML (enlever les balises)
                    key = re.sub(r'<[^>]+>', '', key).strip()
                    print(f"🔑 Clé trouvée: '{key}'")
                    
                    # Extraire la valeur - priorité aux balises internes
                    value_element = item.find_element(By.CSS_SELECTOR, ".specs-table-td")
                    try:
                        # Essayer d'abord les paragraphes
                        value_p = value_element.find_element(By.TAG_NAME, "p")
                        value = value_p.get_attribute("innerHTML").strip()
                        value = re.sub(r'<[^>]+>', '', value).strip()
                    except:
                        try:
                            # Essayer les listes
                            value_list = value_element.find_elements(By.TAG_NAME, "li")
                            if value_list:
                                value = "; ".join([li.get_attribute("innerHTML").strip() for li in value_list])
                                value = re.sub(r'<[^>]+>', '', value).strip()
                            else:
                                # Fallback : innerHTML direct
                                value = value_element.get_attribute("innerHTML").strip()
                                value = re.sub(r'<[^>]+>', '', value).strip()
                        except:
                            # Fallback final
                            value = value_element.get_attribute("innerHTML").strip()
                            value = re.sub(r'<[^>]+>', '', value).strip()
                    print(f"📄 Valeur trouvée: '{value}'")
                    
                    # Nettoyer la valeur (supprimer les sauts de ligne multiples)
                    value = ' '.join(value.split())
                    
                    if key and value:
                        detailed_specs[key] = value
                        print(f"✅ Spec ajoutée: {key} = {value}")
                    else:
                        print(f"⚠️ Spec ignorée - clé vide: {not key}, valeur vide: {not value}")
                        
                except Exception as e:
                    print(f"⚠️ Erreur lors de l'extraction d'un item: {e}")
                    continue
                    
            print(f"✅ {len(detailed_specs)} spécifications extraites avec succès")
            
            # Fallback : essayer avec d'autres sélecteurs si aucune spec trouvée
            if not detailed_specs:
                fallback_selectors = [
                    ".tech_specs_inner .specs-table .item",
                    ".specs-wrapper .item", 
                    ".product-specs tr",
                    ".specifications tr"
                ]
                
                for selector in fallback_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            print(f"🔍 Fallback: Trouvé {len(elements)} éléments avec {selector}")
                            
                            for element in elements:
                                try:
                                    # Essayer d'extraire clé-valeur
                                    key_elem = element.find_element(By.CSS_SELECTOR, ".specs-table-th, .spec-title, td:first-child, th:first-child")
                                    value_elem = element.find_element(By.CSS_SELECTOR, ".specs-table-td, .spec_text, td:last-child, td:nth-child(2)")
                                    
                                    key = key_elem.text.strip()
                                    value = value_elem.text.strip()
                                    
                                    if key and value and len(key) < 100:
                                        detailed_specs[key] = ' '.join(value.split())
                                        
                                except Exception:
                                    continue
                            
                            if detailed_specs:
                                break
                                
                    except Exception:
                        continue
                        
        except Exception as e:
            print(f"⚠️ Erreur lors de l'extraction des spécifications: {e}")
            
        # Afficher quelques spécifications pour le débogage
        if detailed_specs:
            print("🔍 Exemples de spécifications extraites:")
            for i, (key, value) in enumerate(list(detailed_specs.items())[:3]):
                print(f"  - {key}: {value[:100]}...")
        else:
            print("❌ Aucune spécification extraite")
            
    except Exception as e:
        print(f"❌ Erreur générale lors de l'extraction de {product_name}: {e}")
    
    finally:
        # Fermer l'onglet et revenir à l'onglet principal
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(original_window)
        except:
            pass
            
    return detailed_specs

def extract_detailed_tech_specs(driver, wait, product_link, product_name):
    """Accède à la page produit et extrait les spécifications techniques détaillées"""
    detailed_specs = {}
    original_window = driver.current_window_handle
    
    try:
        # Ouvrir dans un nouvel onglet
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        
        print(f"🔍 Accès aux détails: {product_name}")
        driver.get(product_link)
        
        # Attendre le chargement
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(DELAY_FOR_PAGE_LOAD)
        
        # Chercher et cliquer sur l'onglet Tech Specs
        tech_specs_clicked = False
        tech_specs_selectors = [
            "section[name='tech_specs'] .title",
            ".tech_specs_container .title",
            "//div[contains(text(), 'Tech Specs')]",
            "//button[contains(text(), 'Tech Specs')]",
            "[data-tkey='haloSubseriesTechSpecs']"
        ]
        
        for selector in tech_specs_selectors:
            try:
                if selector.startswith("//"):
                    tech_specs_btn = driver.find_element(By.XPATH, selector)
                else:
                    tech_specs_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    
                if tech_specs_btn.is_displayed():
                    driver.execute_script("arguments[0].click();", tech_specs_btn)
                    print("📊 Onglet Tech Specs activé")
                    tech_specs_clicked = True
                    time.sleep(2)
                    break
            except:
                continue
                
        # Extraire les spécifications depuis le tableau
        try:
            # Attendre que le contenu des specs soit visible
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".specs-table, .tech_specs_inner")))
            
            # Méthode 1: Tableau structuré (format de votre exemple)
            spec_items = driver.find_elements(By.CSS_SELECTOR, ".specs-table .item")
            
            for item in spec_items:
                try:
                    title_elem = item.find_element(By.CSS_SELECTOR, ".specs-table-th .spec-title")
                    value_elem = item.find_element(By.CSS_SELECTOR, ".specs-table-td")
                    
                    title = title_elem.text.strip()
                    
                    # Extraire le texte - priorité aux balises internes (p, ul, li)
                    value = ""
                    try:
                        # Essayer d'abord les paragraphes
                        value_p = value_elem.find_element(By.TAG_NAME, "p")
                        value = value_p.text.strip()
                    except:
                        try:
                            # Essayer les listes
                            value_list = value_elem.find_elements(By.TAG_NAME, "li")
                            if value_list:
                                value = "; ".join([li.text.strip() for li in value_list])
                            else:
                                # Fallback : texte direct
                                value = value_elem.text.strip()
                        except:
                            # Fallback final
                            value = value_elem.text.strip()
                    
                    if title and value:
                        detailed_specs[title] = value
                except:
                    continue
                    
            # Méthode 2: Si pas de tableau structuré, chercher d'autres formats
            if not detailed_specs:
                # Chercher dans des divs ou sections alternatives
                alt_selectors = [
                    ".tech_specs_inner",
                    ".specifications",
                    ".product-specs", 
                    ".spec-content"
                ]
                
                for selector in alt_selectors:
                    try:
                        spec_container = driver.find_element(By.CSS_SELECTOR, selector)
                        spec_text = spec_container.text
                        
                        # Parser le texte pour extraire des patterns clé:valeur
                        patterns = [
                            r'([^:\n]+):\s*([^\n]+)',
                            r'([^-\n]+)-\s*([^\n]+)'
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, spec_text, re.MULTILINE)
                            for match in matches:
                                key, value = match[0].strip(), match[1].strip()
                                if len(key) < 100 and len(value) < 500:
                                    detailed_specs[key] = value
                        break
                    except:
                        continue
                        
            print(f"📊 {len(detailed_specs)} spécifications extraites")
            
        except Exception as e:
            print(f"⚠️ Erreur extraction specs détaillées: {e}")
            
    except Exception as e:
        print(f"❌ Erreur accès page produit: {e}")
        
    finally:
        # Nettoyer: fermer l'onglet et revenir à l'original
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(original_window)
        except:
            pass
            
    return detailed_specs

def extract_category_from_url(url):
    """Extrait le nom de la catégorie depuis l'URL"""
    category_mapping = {
        "dg-series-all-flash": "DG Series All-Flash Storage",
        "dm-series-all-flash": "DM Series All-Flash Storage", 
        "dm-series-hybrid-flash": "DM Series Hybrid Flash Storage",
        "de-hybrid-flash-array": "DE Hybrid Flash Array",
        "das": "Direct Attached Storage (DAS)",
        "san-fibre-channel-switches": "SAN Fibre Channel Switches"
    }
    
    for key, category in category_mapping.items():
        if key in url:
            return category
            
    return "Storage Solutions"

def scrape_all_lenovo_storage():
    """Fonction principale pour scraper tout le stockage Lenovo"""
    print("🚀 Démarrage du scraping Lenovo Storage")
    all_products = []
    
    for i, category_url in enumerate(STORAGE_URLS, 1):
        try:
            print(f"\n📂 [{i}/{len(STORAGE_URLS)}] Traitement catégorie: {extract_category_from_url(category_url)}")
            
            # Extraire les produits de cette catégorie
            category_products = extract_products_from_category_page(driver, wait, category_url)
            all_products.extend(category_products)
            
            print(f"✅ Catégorie {i} terminée - {len(category_products)} produits extraits")
            
            # Pause entre catégories
            if i < len(STORAGE_URLS):
                print(f"⏳ Pause de {DELAY_BETWEEN_CATEGORIES}s entre catégories...")
                time.sleep(DELAY_BETWEEN_CATEGORIES)
                
        except Exception as e:
            print(f"❌ Erreur catégorie {i}: {e}")
            continue
    
    # Supprimer les doublons basés sur le lien
    unique_products = []
    seen_links = set()
    
    for product in all_products:
        if product['link'] not in seen_links:
            unique_products.append(product)
            seen_links.add(product['link'])
    
    print(f"\n🎯 Extraction Lenovo Storage terminée!")
    print(f"📊 {len(all_products)} produits trouvés au total")
    print(f"🔗 {len(unique_products)} produits uniques après déduplication")
    
    return unique_products

if __name__ == "__main__":
    try:
        products = scrape_all_lenovo_storage()
        
        if products:
            # Sauvegarder en JSON
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=4)
            print(f"💾 Données sauvegardées dans {OUTPUT_JSON}")
            
            # Sauvegarde en base de données conditionnelle
            if ENABLE_DB:
                try:
                    save_to_database(OUTPUT_JSON, "stockage", BRAND)
                    print("✅ Sauvegarde en base de données réussie!")
                except Exception as e:
                    print(f"❌ Erreur sauvegarde base de données: {e}")
                    print("💡 Assurez-vous que MySQL est installé et configuré")
            else:
                print("ℹ️ Sauvegarde BD désactivée (ENABLE_DB=false)")
        else:
            print("⚠️ Aucun produit n'a été extrait.")
            
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
    finally:
        driver.quit()
