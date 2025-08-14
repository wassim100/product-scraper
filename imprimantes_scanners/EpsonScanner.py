from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
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

# ✅ CONFIGURATION EPSON SCANNERS
BRAND = "EPSON"
OUTPUT_JSON = "epson_scanners_full.json"
CHROMEDRIVER_PATH = os.path.join(os.path.dirname(__file__), "..", "chromedriver.exe")
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").lower() == "true"
JITTER_RANGE = (0.8, 1.6)
# Si lancé par le scheduler, on laisse le scheduler gérer l'insertion DB pour éviter les doublons
RUNNING_UNDER_SCHEDULER = os.getenv("RUNNING_UNDER_SCHEDULER", "0") in {"1", "true", "True"}
ENABLE_DB = (os.getenv("ENABLE_DB", "false").lower() == "true") and not RUNNING_UNDER_SCHEDULER  # Laisser à false en test
MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "0"))  # 0 = pas de limite

# Delais
DELAY_FOR_PAGE_LOAD = 3

# 📦 URLs catégories Scanners Epson
BASE_URLS = {
    "Photo & Graphic": "https://epson.com/For-Home/Scanners/Photo-%26-Graphic-Scanners/c/nc220",
    "Receipt": "https://epson.com/For-Work/Scanners/Receipt-Scanners/c/w280",
    "Document (Work)": "https://epson.com/For-Work/Scanners/Document-Scanners/c/w241",
    "Document (Global Filter)": "https://epson.com/Scanners/c/e2?q=%3Aprice-asc%3AdiscontinuedFlag%3Afalse%3AinStockFlag%3Atrue%3AScanners+Facets%2CPrimary+Use%3ADocuments&text=",
}

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

        # Fallback Selenium Manager si chromedriver.exe absent
        if os.path.exists(CHROMEDRIVER_PATH):
            service = Service(CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=options)
        else:
            driver = webdriver.Chrome(options=options)

        # Anti-détection
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.implicitly_wait(10)
        return driver
    except Exception as e:
        print(f"❌ Erreur configuration driver: {e}")
        return None

def handle_cookies_popup(driver):
    """Gère les popups de cookies"""
    try:
        cookie_selectors = [
            "button[id*='cookie']",
            "button[class*='cookie']",
            "button[id*='accept']",
            "button[class*='accept']",
            ".cookie-accept",
            "#cookie-accept",
            ".accept-cookies",
            "#accept-cookies",
        ]
        for selector in cookie_selectors:
            try:
                btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                btn.click()
                print("✅ Popup cookies fermé")
                time.sleep(1)
                return True
            except Exception:
                continue
    except Exception as e:
        print(f"⚠️ Pas de popup cookies détecté: {e}")
    return False

def extract_product_links_for_url(driver, category_name: str, listing_url: str):
    """Extrait les liens produits pour une URL de catégorie (avec pagination)."""
    links = []
    current_page = 1
    try:
        print(f"\n🌐 Catégorie: {category_name}")
        driver.get(listing_url)
        try:
            WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            time.sleep(DELAY_FOR_PAGE_LOAD)
        handle_cookies_popup(driver)

        while True:
            print(f"📄 === PAGE {current_page} ({category_name}) ===")
            grid_locator = (By.CSS_SELECTOR, "ul.product-listing.product-grid")
            WebDriverWait(driver, 20).until(EC.presence_of_element_located(grid_locator))

            products = driver.find_elements(By.CSS_SELECTOR, "li.product-item")
            first_item = products[0] if products else None
            print(f"📦 {len(products)} produits trouvés")

            for product in products:
                try:
                    sku = product.get_attribute("data-tl_sku")
                    # Lien
                    link_el = product.find_element(By.CSS_SELECTOR, "a.thumb")
                    url = link_el.get_attribute("href")
                    if url and url.startswith('/'):
                        url = "https://epson.com" + url
                    # Nom
                    name_el = product.find_element(By.CSS_SELECTOR, "a.name.productname")
                    name = name_el.get_attribute("title")
                    # Prix
                    try:
                        price = product.find_element(By.CSS_SELECTOR, ".amount.productamount").text.strip()
                    except Exception:
                        price = "Prix non disponible"
                    # Image
                    try:
                        image_url = product.find_element(By.CSS_SELECTOR, "img.lazyOwl").get_attribute("src")
                    except Exception:
                        image_url = ""
                    # Reviews
                    try:
                        reviews = product.find_element(By.CSS_SELECTOR, ".bv_numReviews_component_container .bv_text").text.strip()
                    except Exception:
                        reviews = ""

                    if url and sku:
                        links.append({
                            'sku': sku,
                            'name': name,
                            'url': url,
                            'price': price,
                            'image_url': image_url,
                            'reviews': reviews,
                            'category': category_name,
                        })
                        print(f"✅ Produit ajouté: {name} - {sku}")
                except Exception as e:
                    print(f"⚠️ Erreur extraction produit: {e}")
                    continue

            # Pagination: bouton next
            try:
                next_selectors = [
                    "a.next:not(.disabled)",
                    "a[title='next']:not(.disabled)",
                    "a[data-action='next']:not(.disabled)",
                    ".pager a.next:not(.disabled)",
                ]
                next_button = None
                for sel in next_selectors:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, sel)
                        if el and el.is_enabled():
                            next_button = el
                            break
                    except Exception:
                        continue

                if next_button and next_button.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_button)
                    time.sleep(random.uniform(*JITTER_RANGE))
                    try:
                        next_button.click()
                    except ElementClickInterceptedException:
                        driver.execute_script("arguments[0].click();", next_button)
                    except Exception:
                        driver.execute_script("arguments[0].click();", next_button)

                    if first_item is not None:
                        try:
                            WebDriverWait(driver, 20).until(EC.staleness_of(first_item))
                        except TimeoutException:
                            WebDriverWait(driver, 20).until(EC.presence_of_element_located(grid_locator))
                    else:
                        WebDriverWait(driver, 20).until(EC.presence_of_element_located(grid_locator))

                    current_page += 1
                    print(f"🔄 Page suivante: {current_page}")
                else:
                    print("✅ Dernière page atteinte")
                    break
            except Exception as e:
                print(f"⚠️ Erreur pagination: {e}")
                break

        return links
    except Exception as e:
        print(f"❌ Erreur sur la catégorie {category_name}: {e}")
        return links

def extract_product_details(driver, info: dict):
    """Extrait détails d'un scanner depuis sa page."""
    try:
        print(f"🔍 Extraction détails: {info['name']}")
        driver.get(info['url'])
        try:
            WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            time.sleep(DELAY_FOR_PAGE_LOAD)
        time.sleep(random.uniform(*JITTER_RANGE))

        data = {
            'brand': BRAND,
            'category': info.get('category', ''),
            'link': info['url'],
            'name': info['name'],
            'tech_specs': "",
            'scraped_at': datetime.now().isoformat(),
            'datasheet_link': "",
            'sku': info.get('sku', ''),
            'price': info.get('price', ''),
            'image_url': info.get('image_url', ''),
            'reviews': info.get('reviews', ''),
        }

        # Détails / specs (réutilise les sélecteurs éprouvés)
        try:
            detail_selectors = [
                ".details",
                ".description .details",
                ".pdp-product-highlights-content .details",
                ".details-section-wrapper .details",
                ".product-highlights .details",
            ]
            details_section = None
            for sel in detail_selectors:
                try:
                    details_section = driver.find_element(By.CSS_SELECTOR, sel)
                    print(f"✅ Section détails trouvée avec: {sel}")
                    break
                except Exception:
                    continue

            if details_section:
                items = details_section.find_elements(By.CSS_SELECTOR, "ul li, li")
                specs = []
                for it in items:
                    t = it.text.strip()
                    if t:
                        # Nettoyage doux (conserve les chiffres utiles)
                        t = re.sub(r"\s*[\*\†‡]+$", "", t)
                        t = re.sub(r"\s*\((?:Note|footnote)?\d+\)\s*$", "", t, flags=re.I)
                        t = re.sub(r"\s*\[\d+\]\s*$", "", t)
                        t = t.strip()
                        if t:
                            specs.append(t)
                if specs:
                    data['tech_specs'] = " | ".join(specs)
                print(f"✅ {len(specs)} spécifications techniques extraites")
            else:
                print("⚠️ Section détails introuvable")
        except Exception as e:
            print(f"⚠️ Erreur extraction specs: {e}")

        # PDF / datasheet
        try:
            print("📄 Recherche PDF…")
            pdf_found = False
            pdf_selectors = [
                "a[href*='.pdf']",
                "a[href*='ImConvServlet']",
                "a[href*='specification']",
                "a[href*='datasheet']",
            ]
            for sel in pdf_selectors:
                try:
                    links = driver.find_elements(By.CSS_SELECTOR, sel)
                    for a in links:
                        href = a.get_attribute("href")
                        if not href:
                            continue
                        if any(k in href.lower() for k in ["specification", "datasheet", "spec"]):
                            if not any(bad in href.lower() for bad in ["catalog", "education", "brochure"]):
                                data['datasheet_link'] = href
                                pdf_found = True
                                print(f"✅ PDF trouvé: {href}")
                                break
                    if pdf_found:
                        break
                except Exception:
                    continue
            if not pdf_found:
                for sel in pdf_selectors:
                    try:
                        links = driver.find_elements(By.CSS_SELECTOR, sel)
                        for a in links:
                            href = a.get_attribute("href")
                            if href and not any(bad in href.lower() for bad in ["catalog", "education", "brochure"]):
                                data['datasheet_link'] = href
                                pdf_found = True
                                print(f"✅ PDF général trouvé: {href}")
                                break
                        if pdf_found:
                            break
                    except Exception:
                        continue
            if not pdf_found:
                print("⚠️ Aucun PDF trouvé")
        except Exception as e:
            print(f"⚠️ Erreur recherche PDF: {e}")

        # Résumé
        print("📋 Résumé:")
        print(f"   • Brand: {data['brand']}")
        print(f"   • Catégorie: {data['category']}")
        print(f"   • Name: {data['name']}")
        print(f"   • Link: {data['link']}")
        print(f"   • Tech specs: {'✅' if data['tech_specs'] else '❌'}")
        print(f"   • Datasheet link: {'✅' if data['datasheet_link'] else '❌'}")
        print(f"   • Scraped at: {data['scraped_at']}")

        return data
    except Exception as e:
        print(f"❌ Erreur détails: {e}")
        return None

def scrape_epson_scanners():
    driver = setup_driver()
    if not driver:
        return []

    all_links = []
    all_products = []
    try:
        # Collecte des liens par catégorie
        for category, url in BASE_URLS.items():
            cat_links = extract_product_links_for_url(driver, category, url)
            all_links.extend(cat_links)

        # Déduplication (sku prioritaire, sinon URL)
        seen = set()
        deduped = []
        for p in all_links:
            key = (p.get('sku') or '').strip() or p['url']
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        print(f"\n📊 Total produits (dédupliqués): {len(deduped)}")

        # Limiter pour démo si demandé
        if MAX_PRODUCTS > 0:
            deduped = deduped[:MAX_PRODUCTS]
            print(f"🔬 Limite appliquée: {len(deduped)} produits")

        # Extraction détails
        for i, info in enumerate(deduped, 1):
            print(f"\n📦 Traitement produit {i}/{len(deduped)}")
            try:
                details = extract_product_details(driver, info)
                if details:
                    all_products.append(details)
                    print("✅ Produit traité")
                else:
                    print("❌ Échec produit")
                time.sleep(1.5)
            except Exception as e:
                print(f"❌ Erreur produit {i}: {e}")
                continue
        return all_products
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        return all_products
    finally:
        try:
            driver.quit()
            print("🔚 Driver fermé")
        except Exception:
            pass

def save_results(products_data):
    if not products_data:
        print("❌ Aucune donnée à sauvegarder")
        return False
    try:
        json_path = os.path.join(os.path.dirname(__file__), "..", OUTPUT_JSON)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(products_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Données sauvées en JSON: {json_path}")

        if ENABLE_DB:
            try:
                # Sauvegarder en base dans la table imprimantes_scanners, filtrée par marque
                res = save_to_database(json_path, 'imprimantes_scanners', BRAND)
                if res is False:
                    print("⚠️ Sauvegarde DB non confirmée")
                else:
                    print("✅ Données sauvées en base de données")
            except Exception as e:
                print(f"⚠️ Erreur sauvegarde DB: {e}")
        else:
            print("⏭️ Sauvegarde base de données désactivée (mode test)")
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")
        return False

def main():
    print("=" * 60)
    print("🖨️  EPSON SCANNERS SCRAPER")
    print("=" * 60)
    if RUNNING_UNDER_SCHEDULER:
        print("🤖 Lancement sous scheduler: insertion DB gérée par le scheduler")
    print(f"DB interne activée: {'oui' if ENABLE_DB else 'non'}")
    start = datetime.now()

    products = scrape_epson_scanners()
    if products:
        save_results(products)
        end = datetime.now()
        duration = end - start
        print("\n" + "=" * 60)
        print("📊 RÉSUMÉ DU SCRAPING")
        print("=" * 60)
        print(f"✅ Produits extraits: {len(products)}")
        print(f"⏱️  Durée totale: {duration}")
        print(f"📁 Fichier JSON: {OUTPUT_JSON}")
        specs_ok = sum(1 for p in products if p.get('tech_specs'))
        pdf_ok = sum(1 for p in products if p.get('datasheet_link'))
        print("📊 STATISTIQUES:")
        if products:
            print(f"   • Spécifications extraites: {specs_ok}/{len(products)} ({(specs_ok/len(products))*100:.1f}%)")
            print(f"   • PDFs trouvés: {pdf_ok}/{len(products)} ({(pdf_ok/len(products))*100:.1f}%)")
        print("=" * 60)
    else:
        print("\n❌ Aucune donnée extraite")

if __name__ == "__main__":
    main()
