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
from urllib.parse import urlparse, parse_qs

# Ajouter le chemin du module database
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.mysql_connector import save_to_database

# ✅ CONFIGURATION HP IMPRIMANTES & SCANNERS (mix sur même page)
BRAND = "HP"
OUTPUT_JSON = "hp_printers_scanners_schema.json"
CHROMEDRIVER_PATH = os.path.join(os.path.dirname(__file__), "..", "chromedriver.exe")
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").lower() == "true"
ENABLE_DB = os.getenv("ENABLE_DB", "false").lower() == "true"
HP_MAX_PRODUCTS = int(os.getenv("HP_MAX_PRODUCTS", "0"))  # 0 = pas de limite
DELAY_FOR_PAGE_LOAD = 3

# 📦 URLs HP (liste mixte imprimantes+scanners) – peut être ajustée au besoin
PRINTER_SCANNER_LISTING = "https://www.hp.com/fr-fr/shop/list.aspx?fc_seg_home=1&sel=prn"  # page listant aussi des scanners/multifonctions

# Mots-clés pour classification et filtrage accessoires
PRINTER_KEYS = [
    "printer", "imprim", "laserjet", "officejet", "deskjet", "smart tank", "smart-tank",
    "pagewide", "envy", "all-in-one", "tout-en-un", "mfp", "multifonction", "multifunction"
]
SCANNER_KEYS = [
    "scanner", "scanjet", "numéris", "numérisation", "scan"
]
ACCESSORY_BLOCKLIST = [
    "cartouche", "cartridge", "toner", "papier", "paper", "maintenance kit", "drum",
    "printhead", "consommable", "consumable", "accessoire", "accessory"
]

# Configuration du scraping
MAX_PRODUCTS_PER_CATEGORY = 3  # Limité pour les tests
DELAY_FOR_PAGE_LOAD = 2

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
        print("✅ Driver Chrome initialisé")
        return driver
    except Exception as e:
        print(f"❌ Erreur initialisation driver: {e}")
        return None

def _text(el):
    try:
        return el.text.strip()
    except Exception:
        return ""

# Raffiner la détection des accessoires (éviter 'Instant Ink' et utiliser des mots complets)
def is_accessory(name: str):
    n = (name or "").lower()
    if "instant ink" in n:
        return False
    patterns = [
        r"\bcartouche(s)?\b", r"\bcartridge(s)?\b", r"\btoner(s)?\b", r"\bpapier\b", r"\bpaper\b",
        r"\bmaintenance\s+kit\b", r"\bdrum(s)?\b", r"\bprinthead\b", r"\bconsommable(s)?\b",
        r"\bconsumable(s)?\b", r"\baccessoire(s)?\b", r"\baccessor(?:y|ies)\b"
    ]
    return any(re.search(p, n, flags=re.I) for p in patterns)

def classify_product_type(name: str, specs_blob: str):
    n = (name or "").lower()
    s = (specs_blob or "").lower()
    def has_any(keys):
        return any(k in n or k in s for k in keys)

    printer = has_any(PRINTER_KEYS)
    scanner = has_any(SCANNER_KEYS)

    if printer and scanner:
        return "MFP", 0.8
    if printer:
        return "PRINTER", 0.7
    if scanner:
        return "SCANNER", 0.7
    return "UNKNOWN", 0.3

def extract_hp_product_schema_info(driver, product_url: str, current: int, total: int):
    """
    Extrait les informations produit HP selon le schéma unifié (comme Epson):
    - brand, link, name, tech_specs (string " | "), scraped_at, datasheet_link
    - champs additionnels: sku, price, image_url, reviews, product_type, classifier_confidence
    """
    try:
        if not product_url:
            print(f"⚠️ [{current}/{total}] URL produit HP vide")
            return None

        print(f"🔍 [{current}/{total}] Extraction HP: {product_url}")
        driver.get(product_url)
        try:
            WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            time.sleep(DELAY_FOR_PAGE_LOAD)

        # Cookies
        try:
            accept = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[id*='cookie'] button, [class*='cookie'] button, button[id*='accept'], button[class*='accept']"))
            )
            accept.click()
            time.sleep(1)
        except Exception:
            pass

        # Nom produit
        name = ""
        for sel in ["h1", "[data-testid*='product-name']", ".product-title", ".product-name"]:
            try:
                t = _text(driver.find_element(By.CSS_SELECTOR, sel))
                if t and len(t) > 3:
                    name = t
                    break
            except Exception:
                continue
        if not name:
            print(f"⚠️ [{current}/{total}] Nom produit introuvable")

        # Prix (best effort)
        price = ""
        for sel in ["[class*='price']", "[data-testid*='price']", "[class*='cost']"]:
            try:
                txt = _text(driver.find_element(By.CSS_SELECTOR, sel))
                if any(sym in txt for sym in ["€", "$", "£"]) and len(txt) < 40:
                    price = txt
                    break
            except Exception:
                continue

        # Image principale
        image_url = ""
        for sel in ["img[alt*='HP']", "img[alt*='Imprim']", "img[alt*='Printer']", "img"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                src = el.get_attribute("src") or el.get_attribute("data-src")
                if src and src.startswith("http"):
                    image_url = src
                    break
            except Exception:
                continue

        # Reviews (best effort)
        reviews = ""
        for sel in ["[data-testid*='reviews']", ".bv_numReviews_component_container .bv_text", "[class*='review']"]:
            try:
                txt = _text(driver.find_element(By.CSS_SELECTOR, sel))
                if txt and any(ch.isdigit() for ch in txt):
                    reviews = txt
                    break
            except Exception:
                continue

        # SKU depuis URL ou page
        sku = ""
        try:
            q = parse_qs(urlparse(product_url).query)
            for key in ["sku", "skuId", "modelNumber", "partnumber", "partNumber"]:
                if key in q and q[key]:
                    sku = q[key][0]
                    break
        except Exception:
            pass
        if not sku:
            for sel in ["[data-sku]", "[data-sku-id]", "[id*='sku']", "[class*='sku']", ".product-sku"]:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                    val = el.get_attribute("data-sku") or _text(el)
                    if val and 3 <= len(val) <= 64:
                        sku = val.strip()
                        break
                except Exception:
                    continue

        # Specs: récupérer listes/bullets
        specs_items = []
        try:
            detail_selectors = [
                ".details", ".description .details", ".pdp-product-highlights-content .details",
                ".details-section-wrapper .details", ".product-highlights .details",
                "section[id*='tech'], section[id*='spec']", "[data-test*='spec']", "[data-testid*='spec']",
                "ul li", "ol li"
            ]
            details_root = None
            for sel in detail_selectors:
                try:
                    details_root = driver.find_element(By.CSS_SELECTOR, sel)
                    break
                except Exception:
                    continue
            lis = []
            if details_root:
                lis = details_root.find_elements(By.CSS_SELECTOR, "li") or []
            if not lis:
                lis = driver.find_elements(By.CSS_SELECTOR, "li")
            for li in lis:
                t = _text(li)
                if t and 3 <= len(t) <= 200:
                    t = re.sub(r"\s*[\*\†‡]+$", "", t)
                    t = re.sub(r"\s*\((?:Note|footnote)?\d+\)\s*$", "", t, flags=re.I)
                    t = re.sub(r"\s*\[\d+\]\s*$", "", t)
                    t = t.strip()
                    if t:
                        specs_items.append(t)
        except Exception:
            pass

        # Si rien trouvé, essayer d'ouvrir l'onglet "Caractéristiques/Spécifications" et parser tables
        if not specs_items:
            try:
                # Cliquer sur l'onglet si présent
                candidate_tab_texts = ["caract", "spécif", "specif", "fiche", "détails", "details"]
                tab_candidates = driver.find_elements(By.CSS_SELECTOR, "button, a, [role='tab'], [data-testid*='tab']")
                for el in tab_candidates:
                    txt = _text(el).lower()
                    if any(k in txt for k in candidate_tab_texts):
                        try:
                            driver.execute_script("arguments[0].click();", el)
                            time.sleep(1)
                            break
                        except Exception:
                            continue
                # Attendre une section specs
                WebDriverWait(driver, 6).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "[class*='spec'], [id*='spec'], [data-testid*='spec']")) > 0)
            except Exception:
                pass
            # Parser tables th/td
            try:
                tables = driver.find_elements(By.CSS_SELECTOR, "table")
                for table in tables:
                    rows = table.find_elements(By.CSS_SELECTOR, "tr")
                    for tr in rows:
                        ths = tr.find_elements(By.CSS_SELECTOR, "th")
                        tds = tr.find_elements(By.CSS_SELECTOR, "td")
                        key = _text(ths[0]) if ths else ""
                        val = _text(tds[-1]) if tds else ""
                        entry = ": ".join([p for p in [key, val] if p])
                        if entry and 3 <= len(entry) <= 200:
                            specs_items.append(entry)
            except Exception:
                pass
            # Parser listes de définitions
            try:
                dls = driver.find_elements(By.CSS_SELECTOR, "dl")
                for dl in dls:
                    dts = dl.find_elements(By.CSS_SELECTOR, "dt")
                    dds = dl.find_elements(By.CSS_SELECTOR, "dd")
                    for i in range(min(len(dts), len(dds))):
                        key = _text(dts[i])
                        val = _text(dds[i])
                        entry = ": ".join([p for p in [key, val] if p])
                        if entry and 3 <= len(entry) <= 200:
                            specs_items.append(entry)
            except Exception:
                pass
            # Dernier recours: blocs de texte 'spec'
            try:
                blocks = driver.find_elements(By.CSS_SELECTOR, "[class*='spec'], [id*='spec']")
                for b in blocks:
                    txt = _text(b)
                    for line in [l.strip() for l in txt.split("\n") if l.strip()]:
                        if 3 <= len(line) <= 200 and ":" in line or "-" in line:
                            specs_items.append(line)
            except Exception:
                pass

        tech_specs = " | ".join(dict.fromkeys([s for s in specs_items if s])) if specs_items else ""

        # PDF / datasheet
        datasheet_link = ""
        try:
            pdf_selectors = [
                "a[href*='.pdf']",
                "a[href*='datasheet']",
                "a[href*='spec']",
                "a[href*='GetPDF.aspx']",
                "a[href*='fiche']",
            ]
            found = False
            for sel in pdf_selectors:
                links = driver.find_elements(By.CSS_SELECTOR, sel)
                for a in links:
                    href = a.get_attribute("href")
                    if not href:
                        continue
                    lh = href.lower()
                    if any(k in lh for k in ["datasheet", "spec", ".pdf", "fiche"]):
                        if not any(b in lh for b in ["brochure", "catalog", "flyer"]):
                            datasheet_link = href
                            found = True
                            break
                if found:
                    break
        except Exception:
            pass

        # Classification produit
        ptype, conf = classify_product_type(name, tech_specs)
        if is_accessory(name):
            ptype = "ACCESSORY"
            conf = 0.95

        product_data = {
            "brand": BRAND,
            "link": product_url.split('#')[0],
            "name": name,
            "tech_specs": tech_specs,
            "scraped_at": datetime.now().isoformat(),
            "datasheet_link": datasheet_link,
            "sku": sku,
            "price": price,
            "image_url": image_url,
            "reviews": reviews,
            "product_type": ptype,
            "classifier_confidence": conf,
        }

        print(f"✅ [{current}/{total}] {name} | type={ptype} | specs={'✅' if tech_specs else '❌'} | pdf={'✅' if datasheet_link else '❌'}")
        return product_data

    except Exception as e:
        print(f"❌ [{current}/{total}] Erreur extraction produit HP: {str(e)}")
        return None

def extract_products_from_listing(driver, listing_url: str):
    """Extrait tous les liens produit depuis une page liste HP (mix imprimantes/scanners)."""
    try:
        print(f"🔗 Accès à la liste HP: {listing_url}")
        driver.get(listing_url)

        # Cookies
        try:
            cookie_selectors = [
                "[id*='onetrust-accept']",
                "[class*='cookie'] button",
                "[id*='cookie-accept']",
            ]
            for selector in cookie_selectors:
                try:
                    btn = WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    btn.click()
                    print("🍪 Cookies acceptés")
                    time.sleep(1)
                    break
                except Exception:
                    continue
        except Exception:
            pass

        # Attente produits
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='product.aspx']"))
            )
        except TimeoutException:
            print("❌ Aucun produit HP détecté")
            return []

        links = []
        cards = driver.find_elements(By.CSS_SELECTOR, "a[href*='product.aspx']")
        for a in cards:
            href = a.get_attribute("href")
            if href and href.startswith("http"):
                base = href.split('#')[0]
                links.append(base)
        # Dédupliquer les liens immédiats
        links = list(dict.fromkeys(links))
        print(f"📦 {len(links)} liens détectés sur la liste")

        # Limite env
        if HP_MAX_PRODUCTS > 0:
            links = links[:HP_MAX_PRODUCTS]
            print(f"🔬 Limite appliquée: {len(links)} liens")

        return links
    except Exception as e:
        print(f"❌ Erreur extraction liste HP: {e}")
        return []

def scrape_all_hp_products():
    driver = setup_driver()
    if not driver:
        return []
    try:
        all_products = []
        links = extract_products_from_listing(driver, PRINTER_SCANNER_LISTING)
        total = len(links)
        for i, url in enumerate(links, 1):
            info = extract_hp_product_schema_info(driver, url, i, total)
            if not info:
                continue
            # Filtrer accessoires
            if info.get("product_type") == "ACCESSORY":
                print("⏭️ Accessoire ignoré")
                continue
            all_products.append(info)
            time.sleep(1)

        # Déduplication (SKU prioritaire, sinon URL sans fragment)
        seen = set()
        unique = []
        for p in all_products:
            key = (p.get('sku') or '').strip() or p['link']
            if key not in seen:
                seen.add(key)
                unique.append(p)
        print(f"📊 Total HP collectés: {len(all_products)} | Uniques: {len(unique)}")
        return unique
    finally:
        try:
            driver.quit()
            print("🔒 Driver WebDriver fermé")
        except Exception:
            pass

if __name__ == "__main__":
    try:
        products = scrape_all_hp_products()
        if products:
            out_path = os.path.join(os.path.dirname(__file__), "..", OUTPUT_JSON)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"💾 Données HP sauvegardées dans {out_path}")

            specs_ok = sum(1 for p in products if p.get('tech_specs'))
            pdf_ok = sum(1 for p in products if p.get('datasheet_link'))
            print("\n📋 RÉSUMÉ:")
            print(f"- {len(products)} produits HP extraits (uniques)")
            print(f"- Specs: {specs_ok}/{len(products)} ({(specs_ok/len(products))*100:.1f}%) | PDFs: {pdf_ok}/{len(products)} ({(pdf_ok/len(products))*100:.1f}%)")

            if ENABLE_DB:
                try:
                    res = save_to_database(out_path, 'imprimantes_scanners', BRAND)
                    if res is False:
                        print("⚠️ Sauvegarde DB non confirmée")
                    else:
                        print("✅ Données HP sauvées en base de données")
                except Exception as e:
                    print(f"⚠️ Erreur sauvegarde DB: {e}")
            else:
                print("⏭️ Sauvegarde base de données désactivée (mode test)")
        else:
            print("⚠️ Aucun produit HP extrait")
    except Exception as e:
        print(f"❌ Erreur fatale HP: {e}")
