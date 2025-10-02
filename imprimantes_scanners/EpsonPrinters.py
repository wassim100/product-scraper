from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
from datetime import datetime
import json
import os
import time
import sys
import re
import random

# Ajouter le chemin du module database
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.mysql_connector import save_to_database

# ✅ CONFIGURATION EPSON IMPRIMANTES & SCANNERS
BRAND = "EPSON"
OUTPUT_JSON = "epson_printers_scanners_full.json"
CHROMEDRIVER_PATH = os.path.join(os.path.dirname(__file__), "..", "chromedriver.exe")
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").lower() == "true"
JITTER_RANGE = (0.8, 1.6)
RUNNING_UNDER_SCHEDULER = os.getenv("RUNNING_UNDER_SCHEDULER", "0") in {"1", "true", "True"}
ENABLE_DB = (os.getenv("ENABLE_DB", "false").lower() == "true") and not RUNNING_UNDER_SCHEDULER
MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "0"))  # 0 = no limit

# Configuration du scraping
DELAY_FOR_PAGE_LOAD = 3

# 📦 URL de base Epson Imprimantes
BASE_URL = "https://epson.com/For-Home/Printers/c/h1?q=%3Aprice-asc%3AdiscontinuedFlag%3Afalse"

def setup_driver():
    """Configuration du driver Chrome avec options anti-détection"""
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        if HEADLESS_MODE:
            options.add_argument("--headless=new")
        
        # Utiliser Selenium Manager par défaut; fallback local si nécessaire
        try:
            driver = webdriver.Chrome(options=options)
        except Exception:
            if os.path.exists(CHROMEDRIVER_PATH):
                service = Service(CHROMEDRIVER_PATH)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                raise
        
        # Script anti-détection
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.implicitly_wait(10)
        return driver
        
    except Exception as e:
        print(f"❌ Erreur configuration driver: {e}")
        return None

def handle_cookies_popup(driver):
    """Gère les popups de cookies"""
    try:
        # Attendre et cliquer sur le bouton d'acceptation des cookies
        cookie_selectors = [
            "button[id*='cookie']",
            "button[class*='cookie']",
            "button[id*='accept']",
            "button[class*='accept']",
            ".cookie-accept",
            "#cookie-accept",
            ".accept-cookies",
            "#accept-cookies"
        ]
        
        for selector in cookie_selectors:
            try:
                cookie_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                cookie_button.click()
                print("✅ Popup cookies fermé")
                time.sleep(2)
                return True
            except:
                continue
                
    except Exception as e:
        print(f"⚠️ Pas de popup cookies détecté: {e}")
    
    return False

def extract_product_links(driver):
    """Extrait les liens des produits depuis toutes les pages avec pagination"""
    all_products_links = []
    current_page = 1
    
    try:
        while True:
            print(f"\n📄 === PAGE {current_page} ===")
            
            # Attendre que la liste des produits se charge
            grid_locator = (By.CSS_SELECTOR, "ul.product-listing.product-grid")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located(grid_locator)
            )
            
            # Extraire tous les produits de la page actuelle
            products = driver.find_elements(By.CSS_SELECTOR, "li.product-item")
            first_item = products[0] if products else None
            print(f"📦 {len(products)} produits trouvés sur la page {current_page}")
            
            page_products = []
            for product in products:  # Traiter TOUS les produits de la page
                try:
                    # SKU du produit
                    sku = product.get_attribute("data-tl_sku")
                    
                    # Lien du produit
                    link_element = product.find_element(By.CSS_SELECTOR, "a.thumb")
                    product_url = link_element.get_attribute("href")
                    
                    # Nom du produit
                    name_element = product.find_element(By.CSS_SELECTOR, "a.name.productname")
                    product_name = name_element.get_attribute("title")
                    
                    # Prix du produit
                    try:
                        price_element = product.find_element(By.CSS_SELECTOR, ".amount.productamount")
                        price = price_element.text.strip()
                    except Exception:
                        price = "Prix non disponible"
                    
                    # Image du produit
                    try:
                        img_element = product.find_element(By.CSS_SELECTOR, "img.lazyOwl")
                        image_url = img_element.get_attribute("src")
                    except Exception:
                        image_url = ""
                    
                    # Notes/Reviews
                    try:
                        reviews_element = product.find_element(By.CSS_SELECTOR, ".bv_numReviews_component_container .bv_text")
                        reviews = reviews_element.text.strip()
                    except Exception:
                        reviews = ""
                    
                    if product_url and sku:
                        # Convertir URL relative en URL absolue
                        if product_url.startswith('/'):
                            product_url = "https://epson.com" + product_url
                        
                        page_products.append({
                            'sku': sku,
                            'name': product_name,
                            'url': product_url,
                            'price': price,
                            'image_url': image_url,
                            'reviews': reviews
                        })
                        
                        print(f"✅ Produit ajouté: {product_name} - {sku}")
                    
                except Exception as e:
                    print(f"⚠️ Erreur extraction produit: {e}")
                    continue
            
            # Ajouter les produits de cette page au total
            all_products_links.extend(page_products)
            print(f"📋 {len(page_products)} produits extraits de la page {current_page}")

            # 🚀 Accélération tests: arrêter la pagination dès que la limite est atteinte
            if MAX_PRODUCTS > 0 and len(all_products_links) >= MAX_PRODUCTS:
                all_products_links = all_products_links[:MAX_PRODUCTS]
                print(f"⏭️ Limite MAX_PRODUCTS atteinte ({MAX_PRODUCTS}), arrêt de la pagination.")
                break
            
            # Chercher le bouton "Next" pour aller à la page suivante
            try:
                # Chercher le lien de pagination suivante
                next_selectors = [
                    "a.next:not(.disabled)",
                    "a[title='next']:not(.disabled)",
                    "a[data-action='next']:not(.disabled)",
                    ".pager a.next:not(.disabled)"
                ]
                
                next_button = None
                for selector in next_selectors:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, selector)
                        if el and el.is_enabled():
                            next_button = el
                            break
                    except NoSuchElementException:
                        continue
                    except Exception:
                        continue
                
                if next_button and next_button.is_enabled():
                    # Scroll vers le bouton next
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_button)
                    time.sleep(random.uniform(*JITTER_RANGE))
                    
                    # Cliquer sur le bouton next
                    try:
                        next_button.click()
                    except ElementClickInterceptedException:
                        driver.execute_script("arguments[0].click();", next_button)
                    except Exception:
                        driver.execute_script("arguments[0].click();", next_button)
                    
                    # Attendre le rechargement réel de la grille (staleness du premier item)
                    if first_item is not None:
                        try:
                            WebDriverWait(driver, 20).until(EC.staleness_of(first_item))
                        except TimeoutException:
                            # Fallback: attendre la présence du grid
                            WebDriverWait(driver, 20).until(EC.presence_of_element_located(grid_locator))
                    else:
                        WebDriverWait(driver, 20).until(EC.presence_of_element_located(grid_locator))
                    
                    current_page += 1
                    print(f"🔄 Navigation vers la page {current_page}")
                else:
                    print("✅ Dernière page atteinte - fin de la pagination")
                    break
                    
            except Exception as e:
                print(f"⚠️ Erreur pagination: {e}")
                print("✅ Fin de la pagination")
                break
        
        print(f"\n📊 RÉSUMÉ PAGINATION:")
        print(f"📄 Total pages parcourues: {current_page}")
        print(f"📦 Total produits extraits: {len(all_products_links)}")
        return all_products_links
        
    except Exception as e:
        print(f"❌ Erreur extraction liens produits: {e}")
        return all_products_links

def extract_product_details(driver, product_info):
    """Extrait les détails complets d'un produit"""
    try:
        print(f"🔍 Extraction détails: {product_info['name']}")
        
        # Naviguer vers la page du produit
        driver.get(product_info['url'])
        # Attendre que le DOM soit prêt plutôt que sleep fixe
        try:
            WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            time.sleep(DELAY_FOR_PAGE_LOAD)
        time.sleep(random.uniform(*JITTER_RANGE))
        
        # Données de base selon le schéma DB
        product_data = {
            'brand': BRAND,
            'link': product_info['url'],
            'name': product_info['name'],
            'tech_specs': "",  # Sera rempli avec les caractéristiques nettoyées (STRING pas liste)
            'scraped_at': datetime.now().isoformat(),
            'datasheet_link': "",  # Lien vers le PDF
            # Données supplémentaires pour compatibilité
            'sku': product_info['sku'],
            'price': product_info['price'],
            'image_url': product_info['image_url'],
            'reviews': product_info['reviews']
        }
        
        # Extraire les caractéristiques techniques - Sélecteurs améliorés
        try:
            # Essayer plusieurs sélecteurs pour la section détails
            details_selectors = [
                ".details",  # Sélecteur original
                ".description .details", # Structure EcoTank/Expression
                ".pdp-product-highlights-content .details", # Structure alternative
                ".details-section-wrapper .details", # Structure complète
                ".product-highlights .details"
            ]
            
            details_section = None
            for selector in details_selectors:
                try:
                    details_section = driver.find_element(By.CSS_SELECTOR, selector)
                    print(f"✅ Section détails trouvée avec: {selector}")
                    break
                except NoSuchElementException:
                    continue
                except Exception:
                    continue
            
            if details_section:
                detail_items = details_section.find_elements(By.CSS_SELECTOR, "ul li, li")
                
                # Nettoyer et structurer les spécifications techniques (ne pas supprimer les chiffres utiles)
                tech_specs_raw = []
                for item in detail_items:
                    detail_text = item.text.strip()
                    if detail_text:
                        # Supprimer seulement les notes de bas de page/astérisques en fin
                        cleaned_text = re.sub(r'\s*[\*\†‡]+$', '', detail_text)
                        cleaned_text = re.sub(r'\s*\((?:Note|footnote)?\d+\)\s*$', '', cleaned_text, flags=re.I)
                        cleaned_text = re.sub(r'\s*\[\d+\]\s*$', '', cleaned_text)
                        cleaned_text = cleaned_text.strip()
                        if cleaned_text:
                            tech_specs_raw.append(cleaned_text)
                
                # Joindre les spécifications en format structuré
                if tech_specs_raw:
                    product_data['tech_specs'] = " | ".join(tech_specs_raw)
                
                print(f"✅ {len(tech_specs_raw)} spécifications techniques extraites")
            else:
                print("⚠️ Aucune section détails trouvée avec les sélecteurs disponibles")
            
        except Exception as e:
            print(f"⚠️ Erreur extraction spécifications: {e}")
        
        # Extraire le lien PDF des spécifications - Logique unifiée simplifiée
        try:
            pdf_found = False
            
            # Stratégie unique : chercher tous les PDFs pertinents sur la page
            print("📄 Recherche PDF...")
            pdf_selectors = [
                "a[href*='.pdf']",
                "a[href*='ImConvServlet']",  # Pattern serveur Epson
                "a[href*='specification']",
                "a[href*='datasheet']"
            ]
            
            for selector in pdf_selectors:
                try:
                    pdf_links = driver.find_elements(By.CSS_SELECTOR, selector)
                    for pdf_link in pdf_links:
                        pdf_url = pdf_link.get_attribute("href")
                        if pdf_url:
                            # Prioriser les PDFs de spécifications et éviter les catalogues
                            if any(keyword in pdf_url.lower() for keyword in ['specification', 'datasheet', 'spec']):
                                if not any(avoid in pdf_url.lower() for avoid in ['catalog', 'education', 'brochure']):
                                    product_data['datasheet_link'] = pdf_url
                                    pdf_found = True
                                    print(f"✅ PDF spécification trouvé: {pdf_url}")
                                    break
                    if pdf_found:
                        break
                except Exception:
                    continue
            
            # Si aucun PDF de spec trouvé, prendre le premier PDF pertinent
            if not pdf_found:
                for selector in pdf_selectors:
                    try:
                        pdf_links = driver.find_elements(By.CSS_SELECTOR, selector)
                        for pdf_link in pdf_links:
                            pdf_url = pdf_link.get_attribute("href")
                            if pdf_url and not any(avoid in pdf_url.lower() for avoid in ['catalog', 'education', 'brochure']):
                                product_data['datasheet_link'] = pdf_url
                                pdf_found = True
                                print(f"✅ PDF général trouvé: {pdf_url}")
                                break
                        if pdf_found:
                            break
                    except Exception:
                        continue
            
            if not pdf_found:
                print("⚠️ Aucun PDF trouvé - ce n'est pas grave")
                    
        except Exception as e:
            print(f"⚠️ Erreur recherche PDF: {e}")
        
        # Afficher un résumé des données extraites selon le schéma DB
        print(f"📋 Résumé extraction:")
        print(f"   • Brand: {product_data['brand']}")
        print(f"   • Name: {product_data['name']}")
        print(f"   • Link: {product_data['link']}")
        print(f"   • Tech specs: {'✅' if product_data['tech_specs'] else '❌'}")
        print(f"   • Datasheet link: {'✅' if product_data['datasheet_link'] else '❌'}")
        print(f"   • Scraped at: {product_data['scraped_at']}")
        
        return product_data
        
    except Exception as e:
        print(f"❌ Erreur extraction détails produit: {e}")
        return None

def scrape_epson_printers():
    """Fonction principale de scraping Epson"""
    driver = setup_driver()
    if not driver:
        return []
    
    all_products = []
    
    try:
        print(f"🚀 Début scraping Epson Imprimantes & Scanners")
        print(f"🌐 Navigation vers: {BASE_URL}")
        
        # Naviguer vers la page principale
        driver.get(BASE_URL)
        time.sleep(DELAY_FOR_PAGE_LOAD)
        
        # Gérer les popups cookies
        handle_cookies_popup(driver)
        
        # Extraire les liens des produits
        product_links = extract_product_links(driver)
        
        if not product_links:
            print("❌ Aucun produit trouvé")
            return []
        
        # Limiter pour démo si demandé
        if MAX_PRODUCTS > 0:
            product_links = product_links[:MAX_PRODUCTS]
            print(f"🔬 Limite appliquée: {len(product_links)} produits")

        # Extraire les détails de chaque produit
        for i, product_info in enumerate(product_links, 1):
            print(f"\n📦 Traitement produit {i}/{len(product_links)}")
            
            try:
                product_details = extract_product_details(driver, product_info)
                
                if product_details:
                    all_products.append(product_details)
                    print(f"✅ Produit {i} traité avec succès")
                else:
                    print(f"❌ Échec traitement produit {i}")
                
                # Pause entre les produits
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ Erreur produit {i}: {e}")
                continue
        
        return all_products
        
    except Exception as e:
        print(f"❌ Erreur générale scraping: {e}")
        return []
    
    finally:
        if driver:
            driver.quit()
            print("🔚 Driver fermé")

def save_results(products_data):
    """Sauvegarde les résultats en JSON et base de données"""
    if not products_data:
        print("❌ Aucune donnée à sauvegarder")
        return False
    
    try:
        # Sauvegarde JSON
        json_path = os.path.join(os.path.dirname(__file__), "..", OUTPUT_JSON)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(products_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Données sauvées en JSON: {json_path}")

        # Sauvegarde base de données (désactivable en mode test)
        if ENABLE_DB:
            try:
                result = save_to_database(json_path, 'imprimantes_scanners', BRAND)
                if result is False:
                    print("⚠️ Sauvegarde base de données non confirmée (retour False)")
                else:
                    print("✅ Données sauvées en base de données")
            except Exception as e:
                print(f"⚠️ Erreur sauvegarde base de données: {e}")
        else:
            print("⏭️ Sauvegarde base de données désactivée (mode test)")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")
        return False

def main():
    """Fonction principale"""
    print("=" * 60)
    print("🖨️  EPSON IMPRIMANTES & SCANNERS SCRAPER")
    print("=" * 60)
    if RUNNING_UNDER_SCHEDULER:
        print("🤖 Lancement sous scheduler: insertion DB gérée par le scheduler")
    print(f"DB interne activée: {'oui' if ENABLE_DB else 'non'}")
    
    start_time = datetime.now()
    
    # Lancer le scraping
    products_data = scrape_epson_printers()
    
    # Sauvegarder les résultats
    if products_data:
        save_results(products_data)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "=" * 60)
        print("📊 RÉSUMÉ DU SCRAPING")
        print("=" * 60)
        print(f"✅ Produits extraits: {len(products_data)}")
        print(f"⏱️  Durée totale: {duration}")
        print(f"📁 Fichier JSON: {OUTPUT_JSON}")
        print(f"📋 Schéma DB respecté:")
        print(f"   • brand: ✅")
        print(f"   • link: ✅") 
        print(f"   • name: ✅")
        print(f"   • tech_specs: ✅")
        print(f"   • scraped_at: ✅")
        print(f"   • datasheet_link: ✅")
        print("=" * 60)
        
        # Statistiques finales
        specs_count = sum(1 for p in products_data if p['tech_specs'])
        pdf_count = sum(1 for p in products_data if p['datasheet_link'])
        
        print(f"📊 STATISTIQUES:")
        print(f"   • Spécifications extraites: {specs_count}/{len(products_data)} ({specs_count/len(products_data)*100:.1f}%)")
        print(f"   • PDFs trouvés: {pdf_count}/{len(products_data)} ({pdf_count/len(products_data)*100:.1f}%)")
        print("=" * 60)
        
    else:
        print("\n❌ Aucune donnée extraite")

if __name__ == "__main__":
    main()
