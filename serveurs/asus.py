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

# Configuration pour tests rapides (doublon conservé mais on honore aussi MAX_PRODUCTS global)
MAX_PAGES_TO_SCRAPE = 2  # ⚡ SEULEMENT 2 PAGES pour test rapide
DELAY_BETWEEN_PRODUCTS = 1  # 1 seconde entre produits
DELAY_BETWEEN_PAGES = 2     # 2 secondes entre pages

# Limite globale produits (via env MAX_PRODUCTS)
try:
    MAX_PRODUCTS_LIMIT = int(os.getenv("MAX_PRODUCTS", "0") or 0)
except Exception:
    MAX_PRODUCTS_LIMIT = 0

# Mode rapide: activé par défaut sous le scheduler
FAST_SCRAPE = os.getenv("FAST_SCRAPE", "true" if os.getenv("RUNNING_UNDER_SCHEDULER") else "false").strip().lower() in {"1","true","yes","on"}

# ✅ Config navigateur avec options améliorées pour éviter la détection
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").strip().lower() in {"1","true","yes","on"}
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.page_load_strategy = 'eager'
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
options.add_argument("--disable-logging")
options.add_argument("--disable-gpu-sandbox")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
if FAST_SCRAPE:
    # Désactiver le chargement des images pour accélérer les pages produit
    options.add_argument("--blink-settings=imagesEnabled=false")
if HEADLESS_MODE:
    # Chrome moderne recommande --headless=new
    options.add_argument("--headless=new")
# Utiliser Selenium Manager (évite les soucis de versions de ChromeDriver)
try:
    driver = webdriver.Chrome(options=options)
except Exception:
    # Fallback minimal si un binaire local est absolument requis
    try:
        local_driver = os.path.join(os.getcwd(), "chromedriver.exe")
        driver = webdriver.Chrome(service=Service(local_driver), options=options)
    except Exception as e:
        raise e
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# Timeout de chargement pour éviter les blocages
try:
    driver.set_page_load_timeout(12 if FAST_SCRAPE else 20)
except Exception:
    pass

# Délais (réduits en mode rapide) pour éviter la détection tout en gardant la vitesse
wait = WebDriverWait(driver, 12 if FAST_SCRAPE else 30)
# Baisser l'attente implicite pour accélérer les find_elements massifs
try:
    driver.implicitly_wait(0.5)
except Exception:
    driver.implicitly_wait(1)

# Utilitaires nettoyage de texte
def _clean(txt):
    if not txt:
        return ""
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip().strip(":-•\u00a0|")

def _merge_spec(specs, key, value):
    key = _clean(key)
    value = _clean(value)
    if not key or not value:
        return
    if len(key) > 120 or len(value) > 2000:
        return
    if key in specs and specs[key] != value:
        # éviter la duplication, concatener proprement
        existing = specs[key]
        if value not in existing:
            specs[key] = f"{existing} | {value}"
    else:
        specs[key] = value

def _derive_sku(product_link: str, name: str) -> str:
    try:
        cand = ""
        if product_link:
            # prendre le dernier segment de l'URL
            parts = re.split(r"[/?#]", product_link)
            for p in reversed(parts):
                if p and "." not in p:
                    cand = p
                    break
            cand = (cand or "").replace("%20", "-").replace("_", "-")
        if not cand and name:
            cand = name
        cand = (cand or "").strip().upper()
        # Normaliser: garder lettres/chiffres et tirets
        cand = re.sub(r"\s+", "-", cand)
        cand = re.sub(r"[^A-Z0-9-]", "", cand)
        # Nettoyer tirets multiples
        cand = re.sub(r"-+", "-", cand).strip("-")
        # Filtre longueur minimale
        if len(cand) < 3:
            return ""
        return cand
    except Exception:
        return ""

COOKIES_ACCEPTED = False

def accept_cookies_if_present(driver):
    global COOKIES_ACCEPTED
    if COOKIES_ACCEPTED:
        return
    try:
        # Cliquer sur les boutons d'acceptation de cookies/consentement
        xpath = (
            "//button[normalize-space() and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'j\'accepte') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accepter'))] | "
            "//a[normalize-space() and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'agree') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ok'))]"
        )
        # OneTrust / standards fréquents
        onetrust = [
            "//*[@id='onetrust-accept-btn-handler']",
            "//*[@id='onetrust-reject-all-handler']",
            "//*[contains(@class,'onetrust-accept')]",
            "//*[contains(@class,'ot-sdk-button') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
        ]
        buttons = driver.find_elements(By.XPATH, xpath)
        for xp in onetrust:
            buttons.extend(driver.find_elements(By.XPATH, xp))
        clicked = False
        for b in buttons[:2]:
            try:
                if b.is_displayed():
                    driver.execute_script("arguments[0].click();", b)
                    time.sleep(0.3 if FAST_SCRAPE else 0.8)
                    clicked = True
            except Exception:
                continue
        if clicked:
            COOKIES_ACCEPTED = True
    except Exception:
        pass

def click_specs_tabs(driver):
    try:
        # Cliquer sur les onglets/boutons/lien contenant des mots clés specs/tech/caract
        keywords = ["spec", "tech", "caract", "caractér", "caracter", "specifications", "specs"]
        cond = " or ".join([f"contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{k}')" for k in keywords])
        xpath = f"//button[{cond}] | //a[{cond}]"
        elems = driver.find_elements(By.XPATH, xpath)
        for el in elems[:3]:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                time.sleep(0.2)
            except Exception:
                pass
            try:
                driver.execute_script("arguments[0].click();", el)
                time.sleep(0.6 if FAST_SCRAPE else 1.2)
            except Exception:
                continue
    except Exception:
        pass

def find_spec_sections(driver):
    sections = []
    try:
        # Viser id/class contenant spec/tech/caract sur section/div
        sect_xpath = (
            "//section[contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'spec') or "
            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'spec') or "
            "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'tech') or "
            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'tech') or "
            "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'caract') or "
            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'caract')] | "
            "//div[contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'spec') or "
            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'spec') or "
            "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'tech') or "
            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'tech') or "
            "contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'caract') or "
            "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'caract')]"
        )
        candidates = driver.find_elements(By.XPATH, sect_xpath)
        # Exclure header/footer/nav/cookies/consent
        bad_words = ["cookie", "consent", "privacy", "youtube", "facebook", "tiktok", "linkedin", "quantcast", "criteo", "awin", "terms", "policy"]
        filtered = []
        for el in candidates:
            try:
                anc = el.find_elements(By.XPATH, "ancestor-or-self::header|ancestor-or-self::footer|ancestor-or-self::nav")
                if anc:
                    continue
                attrs = (el.get_attribute('id') or '') + ' ' + (el.get_attribute('class') or '')
                if any(w in attrs.lower() for w in ["cookie", "consent", "privacy", "banner", "footer", "header", "nav", "subscribe"]):
                    continue
                text_sample = (el.text or '')[:2000].lower()
                if any(w in text_sample for w in bad_words):
                    continue
                filtered.append(el)
            except Exception:
                continue
        # Si rien après filtre, fallback sur 'main' ou article
        if not filtered:
            filtered = driver.find_elements(By.XPATH, "//main | //article")
        sections = filtered
    except Exception:
        sections = []
    return sections

def parse_specs_from_roots(roots):
    specs = {}
    for root in roots:
        try:
            # Tableaux: tr avec th/td
            rows = root.find_elements(By.XPATH, ".//table//tr")
            for r in rows:
                cells = r.find_elements(By.XPATH, "./th|./td")
                if len(cells) >= 2:
                    key = cells[0].text
                    val = " ".join([c.text for c in cells[1:]])
                    _merge_spec(specs, key, val)
        except Exception:
            pass
        try:
            # Listes de définition
            dls = root.find_elements(By.XPATH, ".//dl")
            for dl in dls:
                dts = dl.find_elements(By.TAG_NAME, "dt")
                dds = dl.find_elements(By.TAG_NAME, "dd")
                n = min(len(dts), len(dds))
                for i in range(n):
                    _merge_spec(specs, dts[i].text, dds[i].text)
        except Exception:
            pass
        try:
            # Lignes label/valeur dans li/p/div
            items = root.find_elements(
                By.XPATH,
                ".//*[self::li or self::p or self::div][./strong or ./b or ./span[1]]",
            )
            for it in items:
                try:
                    lbl_el = None
                    for sel in [".//strong[1]", ".//b[1]", ".//span[1]"]:
                        els = it.find_elements(By.XPATH, sel)
                        if els:
                            lbl_el = els[0]
                            break
                    if not lbl_el:
                        continue
                    label = lbl_el.text
                    full = it.text or ""
                    value = full.replace(label, "", 1)
                    # enlever délimiteurs initiaux
                    value = re.sub(r"^[\s:\-–—|]+", "", value)
                    _merge_spec(specs, label, value)
                except Exception:
                    continue
        except Exception:
            pass
    # Nettoyage des entrées indésirables liées aux cookies/politiques
    if specs:
        bad = ["cookie", "policy", "privacy", "youtube", "facebook", "google", "linkedin", "tiktok", "quantcast", "criteo", "awin"]
        specs = {k: v for k, v in specs.items() if not (any(w in (k or '').lower() for w in bad) or any(w in (str(v) or '').lower() for w in bad))}
    return specs

# ✅ Fonction pour extraire les spécifications techniques d'un produit
def extract_product_specs(driver, wait, product_link):
    """Extrait les spécifications techniques d'un produit et une description fallback"""
    try:
        driver.get(product_link)
        # Attendre le chargement de la page
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(0.8 if FAST_SCRAPE else 2.5)

        # Consentement cookies si nécessaire
        accept_cookies_if_present(driver)

        specs_dict = {}

        # Si aucune section specs visible, tenter d'ouvrir onglets specs
        roots = find_spec_sections(driver)
        if not roots:
            click_specs_tabs(driver)
            roots = find_spec_sections(driver)

        # Viser explicitement les blocs specs/tech/caract
        spec_roots = roots
        if not spec_roots:
            # Si rien trouvé, tenter le body entier en dernier recours
            spec_roots = driver.find_elements(By.TAG_NAME, "body")

        specs_from_roots = parse_specs_from_roots(spec_roots)
        specs_dict.update(specs_from_roots)

        # Méthode 3 : Recherche générale (désactivée en mode rapide)
        if not FAST_SCRAPE:
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text
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
                            _merge_spec(specs_dict, key, value)
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

        # Fallback description: si specs vides, capturer une zone de texte pertinente
        fallback_desc = ""
        try:
            if not specs_dict:
                # Essayer une section de caractéristiques/description
                desc_selectors = [
                    ".specifications, .tech-specs, .features, .product-specs, .specs",
                    ".product-description",
                    ".content, .desc, .details",
                ]
                for sel in desc_selectors:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, sel)
                        txt = el.text.strip()
                        if txt and len(txt) > 50:
                            fallback_desc = txt[:4000]
                            break
                    except Exception:
                        continue
                if not fallback_desc:
                    body_txt = driver.find_element(By.TAG_NAME, "body").text
                    fallback_desc = body_txt[:4000]
        except Exception:
            pass

        return specs_dict, datasheet_link, image_url, fallback_desc

    except Exception as e:
        print(f"❌ Erreur lors de l'extraction des specs: {e}")
    return {}, None, "", ""

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
    
    processed_total = 0
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
            
            # Respecter la limite globale MAX_PRODUCTS si définie
            if MAX_PRODUCTS_LIMIT > 0:
                remaining = max(0, MAX_PRODUCTS_LIMIT - len(all_products))
                if remaining == 0:
                    print(f"🛑 Limite MAX_PRODUCTS atteinte ({MAX_PRODUCTS_LIMIT}). Arrêt.")
                    break
                product_items = product_items[:remaining]

            # Traiter les produits de cette page
            page_products = extract_products_from_page(driver, wait, product_items, current_page, len(all_products))
            all_products.extend(page_products)
            processed_total = len(all_products)
            
            print(f"✅ Page {current_page} terminée - Total produits: {len(all_products)}")
            
            # Stop si limite globale atteinte
            if MAX_PRODUCTS_LIMIT > 0 and len(all_products) >= MAX_PRODUCTS_LIMIT:
                print(f"🛑 Limite MAX_PRODUCTS atteinte ({MAX_PRODUCTS_LIMIT}). Arrêt anticipé.")
                break

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

def extract_products_from_page(driver, wait, product_items, page_num, processed_so_far=0):
    """Extrait les produits d'une page donnée"""
    page_products = []
    product_tab_opened = False
    list_tab_handle = driver.current_window_handle
    
    for index, item in enumerate(product_items):
        # Stop si limite globale atteinte
        if MAX_PRODUCTS_LIMIT > 0 and (processed_so_far + len(page_products)) >= MAX_PRODUCTS_LIMIT:
            print("🛑 Limite MAX_PRODUCTS atteinte pendant la page. On s'arrête ici.")
            break
        try:
            # Extraction du nom
            name_element = item.find_element(By.TAG_NAME, "h2")
            name = name_element.text.strip()
            
            # Extraction du lien
            link_element = item.find_element(By.TAG_NAME, "a")
            relative_url = link_element.get_attribute("href")
            product_link = relative_url if relative_url.startswith("http") else BASE + relative_url

            print(f"📦 [Page {page_num}] [{index+1}/{len(product_items)}] Traitement de {name}...")

            # Description courte depuis la carte (fallback si specs indisponibles)
            card_desc = ""
            try:
                p_els = item.find_elements(By.CSS_SELECTOR, ".product_box_item_bottom_con p")
                texts = [ (el.text or "").strip() for el in p_els ]
                # Choisir le plus pertinent: non vide et le plus long
                texts = [t for t in texts if t]
                if texts:
                    card_desc = max(texts, key=len)
                else:
                    card_desc = ""
            except Exception:
                card_desc = ""

            # Gestion d'erreurs plus robuste
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Ouvrir/reutiliser un seul onglet produit
                    if not product_tab_opened:
                        driver.execute_script("window.open('about:blank');")
                        product_tab_opened = True
                    if product_tab_opened and len(driver.window_handles) >= 2:
                        driver.switch_to.window(driver.window_handles[-1])
                    
                    # Utiliser la fonction d'extraction améliorée
                    specs_dict, datasheet_link, image_url, fallback_desc = extract_product_specs(driver, wait, product_link)
                    
                    # Si pas d'image trouvée, essayer l'image de la liste
                    if not image_url:
                        try:
                            driver.switch_to.window(list_tab_handle)
                            image_url = item.find_element(By.TAG_NAME, "img").get_attribute("src")
                            driver.switch_to.window(driver.window_handles[-1])
                        except:
                            image_url = ""
                    
                    # Construire l'objet produit
                    merged_specs = specs_dict if specs_dict else {}
                    if not merged_specs:
                        # Injecter la description comme base de specs (demande utilisateur)
                        desc_text = (card_desc or fallback_desc or "").strip()
                        if desc_text:
                            merged_specs = {"raw_text": desc_text}

                    sku_val = _derive_sku(product_link, name)

                    product_data = {
                        "brand": "Asus",
                        "link": product_link,
                        "name": name,
                        "sku": sku_val,
                        "tech_specs": merged_specs,
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
                        # Ne pas fermer l'onglet produit, revenir à la liste
                        driver.switch_to.window(list_tab_handle)
                        
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
                driver.switch_to.window(list_tab_handle)
            except:
                pass
            
            # Pause pour éviter la surcharge
            time.sleep(0.3 if FAST_SCRAPE else DELAY_BETWEEN_PRODUCTS)

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
    
    # Nettoyage: fermer l'onglet produit si ouvert
    try:
        if product_tab_opened and len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            driver.close()
            driver.switch_to.window(list_tab_handle)
    except Exception:
        pass
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
