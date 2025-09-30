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
import traceback

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
# Laisser Selenium Manager gérer automatiquement ChromeDriver (évite les incompatibilités)

# --- CONFIGURATION POUR LE TEST ---
# Ces délais sont conservés pour un scraping respectueux
DELAY_BETWEEN_PRODUCTS = 2
DELAY_BETWEEN_PAGES = 5 # Délai entre chaque catégorie

# --- SETUP SELENIUM ---
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
# Optional DB import: keep scraper runnable without local package resolution
try:
    from database.mysql_connector import save_to_database  # type: ignore
    _DB_IMPORT_OK = True
except Exception:
    save_to_database = None  # type: ignore
    _DB_IMPORT_OK = False
ENABLE_DB = os.getenv("ENABLE_DB", "false").lower() == "true"
FAST_SCRAPE = os.getenv("FAST_SCRAPE", "false").strip().lower() in {"1","true","yes","on"}
SKIP_PDP_ENRICH = os.getenv("SKIP_PDP_ENRICH", "true" if FAST_SCRAPE else "false").strip().lower() in {"1","true","yes","on"}

HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").strip().lower() in {"1","true","yes","on"}
options = webdriver.ChromeOptions()
options.page_load_strategy = 'eager'
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
options.add_argument("--log-level=3")
options.add_argument("--disable-notifications")
# Disable images in FAST_SCRAPE to speed up
if FAST_SCRAPE:
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
# Utiliser Selenium Manager (pas de chemin explicite vers chromedriver)
if HEADLESS_MODE:
    options.add_argument("--headless=new")

try:
    driver = webdriver.Chrome(options=options)
except Exception:
    # Fallback minimal si nécessaire (chemin local si présent)
    try:
        local_driver = os.path.join(os.getcwd(), "chromedriver.exe")
        driver = webdriver.Chrome(service=Service(local_driver), options=options)
    except Exception as e:
        raise e
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
try:
    driver.set_page_load_timeout(12 if FAST_SCRAPE else 20)
except Exception:
    pass
driver.implicitly_wait(3 if FAST_SCRAPE else 10)
wait = WebDriverWait(driver, 10 if FAST_SCRAPE else 20)

# --- FONCTIONS DE SCRAPING (ADAPTÉES POUR HP) ---

def handle_cookie_banner(driver, wait):
    """Tente de trouver et de cliquer sur la bannière de cookies."""
    try:
        # HP utilise souvent OneTrust pour les cookies. On cible le bouton d'acceptation.
        cookie_button = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        print("INFO: Bannière de cookies trouvée. Clic sur 'Accept'.")
        cookie_button.click()
        time.sleep(1 if FAST_SCRAPE else 2) # Laisser le temps à la page de se recharger/réorganiser après le clic.
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
        time.sleep(1 if FAST_SCRAPE else 2) # Laisser le temps au dialogue de se fermer.
    except TimeoutException:
        print("INFO: Pas de bannière de région trouvée, ou déjà fermée.")
    except Exception as e:
        print(f"AVERTISSEMENT: Erreur en essayant de gérer la bannière de région: {e}")


# La fonction extract_product_specs a été supprimée car elle n'est plus nécessaire avec l'approche JSON-LD

def _clean_link(url: str) -> str:
    """Normalise un lien produit: supprime ancres/fragments (#reviews), garde absolu."""
    if not url:
        return ""
    try:
        # Supprimer l'ancre et le trailing slash superflu
        base = url.split('#')[0]
        # HP retourne parfois des liens relatifs
        if base.startswith('/'):
            return BASE_URL.rstrip('/') + base
        return base
    except Exception:
        return url

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()

def _sku_from_img(src: str) -> str | None:
    """Extrait un SKU probable depuis un nom de fichier image (ex: .../jk0963.png -> JK0963)."""
    if not src:
        return None
    m = re.search(r"/([a-z]{2}\d{4,})\.[a-z]+(?:\?.*)?$", src, flags=re.I)
    if m:
        return m.group(1).upper()
    return None

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
        time.sleep(1 if FAST_SCRAPE else 3)  # Laisser le temps pour que tous les scripts s'exécutent

        # ÉTAPE 1: Extraire les liens des produits depuis les éléments HTML (avec hints fiables)
        print("🔗 Extraction des liens produits...")
        product_links_data = []
        seen_links = set()
        product_links_data = []
        # 1) Parcourir les cartes produit (plus robuste et rapide)
        try:
            try:
                max_products_env = int(os.getenv("MAX_PRODUCTS", "0") or "0")
            except ValueError:
                max_products_env = 0

            cards = driver.find_elements(By.CSS_SELECTOR, "[data-test-hook='@hpstellar/core/product-tile']")
            print(f"🧩 {len(cards)} cartes produit détectées")
            for idx, card in enumerate(cards):
                if max_products_env and len(product_links_data) >= max_products_env:
                    break
                try:
                    href = ''
                    try:
                        title_link = card.find_element(By.CSS_SELECTOR, "a[data-test-hook='@hpstellar/core/product-tile__title']")
                        href = _clean_link(title_link.get_attribute('href'))
                    except Exception:
                        try:
                            any_link = card.find_element(By.CSS_SELECTOR, "a[href]")
                            href = _clean_link(any_link.get_attribute('href'))
                        except Exception:
                            href = ''
                    if not href or '#reviews' in href or href in seen_links:
                        continue

                    name_hint = ''
                    try:
                        h2 = card.find_element(By.TAG_NAME, 'h2')
                        name_hint = (h2.text or '').strip()
                    except Exception:
                        try:
                            name_hint = (title_link.text or '').strip()
                        except Exception:
                            name_hint = ''

                    sku_hint = ''
                    try:
                        sku_el = card.find_element(By.CSS_SELECTOR, "[data-test-hook='@hpstellar/core/product-tile__sku']")
                        sku_hint = (sku_el.text or '').strip()
                    except Exception:
                        pass

                    img_hint = ''
                    try:
                        img_el = card.find_element(By.CSS_SELECTOR, "img[data-test-hook='@hpstellar/core/image-with-placeholder'], img")
                        img_hint = (img_el.get_attribute('src') or '').strip()
                    except Exception:
                        pass
                    if not sku_hint and img_hint:
                        ded = _sku_from_img(img_hint)
                        if ded:
                            sku_hint = ded

                    desc_hint = ''
                    try:
                        bullets = card.find_elements(By.XPATH, ".//*[@data-test-hook='@hpstellar/core/product-tile__specs']//li[normalize-space(string()) != '']")
                        lines = []
                        for li in bullets[:6]:
                            t = li.text.strip()
                            if t and 3 < len(t) < 180:
                                lines.append(t)
                        if not lines:
                            paras = card.find_elements(By.XPATH, ".//*[@data-test-hook='@hpstellar/core/product-tile__specs']//p[normalize-space(string()) != '']")
                            for p in paras[:3]:
                                t = p.text.strip()
                                if t and len(t) > 10:
                                    lines.append(t)
                        if lines:
                            seen_txt = set()
                            uniq = []
                            for t in lines:
                                if t not in seen_txt:
                                    uniq.append(t)
                                    seen_txt.add(t)
                            desc_hint = "; ".join(uniq)[:700]
                    except Exception:
                        pass

                    product_links_data.append({
                        'link': href,
                        'name_hint': name_hint,
                        'sku_hint': sku_hint,
                        'img_hint': img_hint,
                        'desc_hint': desc_hint
                    })
                    seen_links.add(href)
                except Exception:
                    continue

            # 2) Fallback aux ancres si aucune carte détectée
            if not product_links_data:
                anchor_selectors = [
                    'a[data-gtm-product-name]',
                    'a[data-gtm-product-sku]',
                    'a[href*="/pdp/"]',
                    'a[href*="/shop/pdp/"]'
                ]
                for sel in anchor_selectors:
                    anchors = driver.find_elements(By.CSS_SELECTOR, sel)
                    for a in anchors:
                        if max_products_env and len(product_links_data) >= max_products_env:
                            break
                        try:
                            href = _clean_link(a.get_attribute('href'))
                            if not href or href in seen_links or '#reviews' in href:
                                continue
                            name_hint = (a.get_attribute('data-gtm-product-name') or a.text or '').strip()
                            sku_hint = (a.get_attribute('data-gtm-product-sku') or a.get_attribute('data-gtm-sku') or '').strip()
                            img_hint = ''
                            try:
                                img = a.find_element(By.XPATH, './/img')
                                img_hint = (img.get_attribute('src') or '').strip()
                            except Exception:
                                pass
                            if not sku_hint and img_hint:
                                ded = _sku_from_img(img_hint)
                                if ded:
                                    sku_hint = ded
                            product_links_data.append({
                                'link': href,
                                'name_hint': name_hint,
                                'sku_hint': sku_hint,
                                'img_hint': img_hint,
                                'desc_hint': ''
                            })
                            seen_links.add(href)
                        except Exception:
                            continue
        except Exception as e:
            print(f"❌ Erreur pendant l'extraction des liens: {e}")
        print(f"🔗 {len(product_links_data)} liens/hints extraits")

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
                def push_product(p):
                    if not isinstance(p, dict):
                        return
                    if p.get('@type') == 'Product':
                        # Normaliser un sous-ensemble utile
                        sku = p.get('sku') or (p.get('gtin13') if isinstance(p.get('gtin13'), str) else None)
                        name = p.get('name')
                        images = p.get('image') or []
                        if isinstance(images, str):
                            images = [images]
                        # Essayer d'obtenir l'URL produit; fallback via offers.url
                        url_prop = p.get('url') or p.get('@id') or ''
                        if not url_prop:
                            offers = p.get('offers')
                            try:
                                if isinstance(offers, dict):
                                    url_prop = offers.get('url') or ''
                                elif isinstance(offers, list):
                                    for off in offers:
                                        if isinstance(off, dict) and off.get('url'):
                                            url_prop = off['url']
                                            break
                            except Exception:
                                pass
                        json_products.append({
                            'raw': p,
                            'sku': sku,
                            'name': name,
                            'images': images,
                            'url': _clean_link(url_prop)
                        })

                if isinstance(json_content, dict) and '@graph' in json_content:
                    for item in json_content['@graph']:
                        push_product(item)
                elif isinstance(json_content, dict) and json_content.get('@type') == 'Product':
                    push_product(json_content)
                elif isinstance(json_content, dict) and json_content.get('@type') == 'ItemList':
                    items = json_content.get('itemListElement', [])
                    for item in items:
                        push_product(item)

            except json.JSONDecodeError:
                print(f"INFO: Script {i+1} ne contenait pas de JSON valide, ignoré.")
                continue
            except Exception as e:
                print(f"❌ Erreur lors du traitement du script {i+1} JSON-LD : {e}")

        print(f"📦 {len(json_products)} produits trouvés dans JSON-LD")

        # ÉTAPE 3: Associer les liens aux données JSON-LD (par URL -> SKU -> nom)
        matched = set()
        used_links = set()

        def first_image(imgs):
            if isinstance(imgs, list) and imgs:
                return imgs[0]
            if isinstance(imgs, str):
                return imgs
            return None

        # Helpers: nettoyage de titre et extraction specs rapides depuis le titre
        def sanitize_name(raw_name: str) -> str:
            try:
                name = (raw_name or '').strip()
                # Retirer sections après tirets multiples qui sont clairement des specs
                # ex: "HPE ProLiant ML350 ... - Xeon Silver 4410Y - 12 Cores - 64GB RAM ..." -> garder la partie avant le premier " - " qui suit le modèle
                parts = [p.strip() for p in name.split(' - ') if p.strip()]
                if len(parts) > 1:
                    # si la 2e partie contient des tokens specs, ne garder que la 1re
                    spec_tokens = ['xeon', 'core', 'cores', 'ram', 'ssd', 'hdd', 'tb', 'gb', 'w power']
                    if any(t in parts[1].lower() for t in spec_tokens):
                        return parts[0]
                # fallback: couper à 120 caractères max pour nom visuel
                return name[:120]
            except Exception:
                return raw_name

        def specs_from_title(raw_name: str) -> dict:
            s = (raw_name or '').lower()
            specs = {}
            # CPU family
            m = re.search(r'(xeon\s+(?:silver|gold|bronze)\s*[\w-]*)', s)
            if m:
                specs['cpu'] = m.group(1).title()
            # Cores
            m = re.search(r'(\d{1,2})\s*cores?', s)
            if m:
                specs['cpu_cores'] = m.group(1)
            # RAM
            m = re.search(r'(\d{1,3})\s*gb\s*ram', s)
            if m:
                specs['memory'] = f"{m.group(1)} GB RAM"
            # Storage
            m = re.search(r'(\d+(?:\.\d+)?)\s*tb\s*hdd', s)
            if m:
                specs['storage'] = f"{m.group(1)} TB HDD"
            m = re.search(r'(\d{1,4})\s*gb\s*ssd', s)
            if m:
                specs['storage_ssd'] = f"{m.group(1)} GB SSD"
            # Power
            m = re.search(r'(\d{3,4})\s*w\s*power', s)
            if m:
                specs['psu'] = f"{m.group(1)} W"
            return specs

        # 3.1 Match par URL exacte/normalisée
        for jp in json_products:
            link = jp.get('url')
            if not link:
                continue
            for pl in product_links_data:
                if pl['link'] == link:
                    matched.add(id(jp))
                    used_links.add(pl['link'])
                    title = jp.get('name') or pl.get('name_hint') or 'Nom non trouvé'
                    base_specs = {**specs_from_title(title)}
                    if not base_specs and pl.get('desc_hint'):
                        base_specs = {"raw_text": pl.get('desc_hint')}
                    page_products.append({
                        "brand": BRAND,
                        "link": pl['link'],
                        "name": sanitize_name(title),
                        "sku": jp.get('sku'),
                        "tech_specs": base_specs,
                        "scraped_at": datetime.now().isoformat(),
                        "datasheet_link": None,
                        "image_url": first_image(jp.get('images')) or pl.get('img_hint')
                    })
                    break

        # 3.2 Match par SKU
        for jp in json_products:
            if id(jp) in matched:
                continue
            sku = jp.get('sku')
            if not sku:
                continue
            for pl in product_links_data:
                if pl['link'] in used_links:
                    continue
                if (pl.get('sku_hint') or '').upper() == sku.upper():
                    matched.add(id(jp))
                    used_links.add(pl['link'])
                    title = jp.get('name') or pl.get('name_hint') or 'Nom non trouvé'
                    base_specs = {**specs_from_title(title)}
                    if not base_specs and pl.get('desc_hint'):
                        base_specs = {"raw_text": pl.get('desc_hint')}
                    page_products.append({
                        "brand": BRAND,
                        "link": pl['link'],
                        "name": sanitize_name(title),
                        "sku": sku,
                        "tech_specs": base_specs,
                        "scraped_at": datetime.now().isoformat(),
                        "datasheet_link": None,
                        "image_url": first_image(jp.get('images')) or pl.get('img_hint')
                    })
                    break

        # 3.3 Match par nom (normalisé)
        for jp in json_products:
            if id(jp) in matched:
                continue
            name_n = _norm(jp.get('name'))
            if not name_n:
                continue
            for pl in product_links_data:
                if pl['link'] in used_links:
                    continue
                if _norm(pl.get('name_hint')) == name_n:
                    matched.add(id(jp))
                    used_links.add(pl['link'])
                    title = jp.get('name') or pl.get('name_hint') or 'Nom non trouvé'
                    base_specs = {**specs_from_title(title)}
                    if not base_specs and pl.get('desc_hint'):
                        base_specs = {"raw_text": pl.get('desc_hint')}
                    page_products.append({
                        "brand": BRAND,
                        "link": pl['link'],
                        "name": sanitize_name(title),
                        "sku": jp.get('sku'),
                        "tech_specs": base_specs,
                        "scraped_at": datetime.now().isoformat(),
                        "datasheet_link": None,
                        "image_url": first_image(jp.get('images')) or pl.get('img_hint')
                    })
                    break

        # 3.4 Ajouter les ancres restantes (sans JSON-LD match) pour ne rien perdre
        for pl in product_links_data:
            if pl['link'] in used_links:
                continue
            title = pl.get('name_hint') or 'Nom non trouvé'
            base_specs = {**specs_from_title(title)}
            if not base_specs and pl.get('desc_hint'):
                base_specs = {"raw_text": pl.get('desc_hint')}
            page_products.append({
                "brand": BRAND,
                "link": pl['link'],
                "name": sanitize_name(title),
                "sku": pl.get('sku_hint'),
                "tech_specs": base_specs,
                "scraped_at": datetime.now().isoformat(),
                "datasheet_link": None,
                "image_url": pl.get('img_hint')
            })
            used_links.add(pl['link'])

        # ÉTAPE 4: Enrichir UNIQUEMENT les produits incomplets en ouvrant la PDP au besoin
        def parse_pdp(url: str) -> dict:
            data = {"name": None, "sku": None, "image_url": None, "tech_specs": {}}
            if not url:
                return data
            current_handle = driver.current_window_handle
            try:
                driver.execute_script("window.open(arguments[0], '_blank');", url)
                driver.switch_to.window(driver.window_handles[-1])
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(2)
                # JSON-LD on PDP
                try:
                    scripts = driver.find_elements(By.XPATH, '//script[@type="application/ld+json"]')
                    for sc in scripts:
                        try:
                            jc = json.loads(sc.get_attribute('innerHTML'))
                        except Exception:
                            continue
                        items = []
                        if isinstance(jc, dict) and '@graph' in jc:
                            items = [x for x in jc['@graph'] if isinstance(x, dict)]
                        elif isinstance(jc, dict):
                            items = [jc]
                        elif isinstance(jc, list):
                            items = jc
                        for it in items:
                            if not isinstance(it, dict):
                                continue
                            if it.get('@type') == 'Product' or ('Product' in str(it.get('@type'))):
                                if not data['name']:
                                    data['name'] = it.get('name')
                                if not data['sku']:
                                    data['sku'] = it.get('sku') or (it.get('gtin13') if isinstance(it.get('gtin13'), str) else None)
                                if not data['image_url']:
                                    imgs = it.get('image')
                                    if isinstance(imgs, list) and imgs:
                                        data['image_url'] = imgs[0]
                                    elif isinstance(imgs, str):
                                        data['image_url'] = imgs
                                break
                except Exception:
                    pass
                # HP Stellar tech-specs blocks
                try:
                    spec_blocks = driver.find_elements(By.CSS_SELECTOR, "[data-test-hook='@hpstellar/pdp/tech-specs__detailedSpec']")
                    specs = {}
                    for blk in spec_blocks:
                        try:
                            label = ''
                            try:
                                label = blk.find_element(By.CSS_SELECTOR, ".FS-FV_gf [data-test-hook='@hpstellar/core/typography']").text.strip()
                            except Exception:
                                # fallback to first heading-like element text
                                label = blk.text.split("\n")[0].strip()
                            value_el = None
                            try:
                                value_el = blk.find_element(By.CSS_SELECTOR, ".FS-FY_gf")
                            except Exception:
                                value_el = blk
                            values = []
                            # Prefer spans with cust-html (may contain lists)
                            for sp in value_el.find_elements(By.CSS_SELECTOR, "span.cust-html"):
                                txt = sp.text.strip()
                                if txt:
                                    values.append(txt)
                            # If still empty, try list items or paragraphs
                            if not values:
                                for li in value_el.find_elements(By.CSS_SELECTOR, "li"):
                                    t = li.text.strip()
                                    if t:
                                        values.append(t)
                            if not values:
                                for p in value_el.find_elements(By.CSS_SELECTOR, "p"):
                                    t = p.text.strip()
                                    if t:
                                        values.append(t)
                            if label and values:
                                # dedupe while preserving order
                                seen = set()
                                uniq = []
                                for v in values:
                                    if v not in seen:
                                        uniq.append(v)
                                        seen.add(v)
                                specs[label] = "; ".join(uniq)
                        except Exception:
                            # Ignore individual block parse errors
                            pass
                    if specs:
                        data['tech_specs'] = specs
                except Exception:
                    pass
            finally:
                try:
                    driver.close()
                    driver.switch_to.window(current_handle)
                except Exception:
                    try:
                        driver.switch_to.window(current_handle)
                    except Exception:
                        pass
            return data

        def enrich_if_needed(prod: dict) -> dict:
            try:
                needs_name = (not prod.get('name')) or (prod.get('name') == 'Nom non trouvé')
                needs_specs = (not isinstance(prod.get('tech_specs'), dict)) or (len(prod.get('tech_specs') or {}) == 0)
                if not (needs_name or needs_specs):
                    return prod
                info = parse_pdp(prod.get('link'))
                # Merge fields conservatively
                if needs_name and info.get('name'):
                    prod['name'] = info['name'][:120]
                if (not prod.get('sku')) and info.get('sku'):
                    prod['sku'] = info['sku']
                if (not prod.get('image_url')) and info.get('image_url'):
                    prod['image_url'] = info['image_url']
                if needs_specs and isinstance(info.get('tech_specs'), dict) and info['tech_specs']:
                    prod['tech_specs'] = info['tech_specs']
                # Minimal fallback if still empty specs
                if not prod.get('tech_specs'):
                    fallback_text = None
                    if isinstance(prod.get('name'), str) and prod['name'] != 'Nom non trouvé':
                        fallback_text = prod['name']
                    prod['tech_specs'] = {"raw_text": fallback_text or ""}
            except Exception:
                pass
            return prod

        if not SKIP_PDP_ENRICH:
            for i in range(len(page_products)):
                page_products[i] = enrich_if_needed(page_products[i])
        else:
            print("⏭️ Enrichissement PDP désactivé (SKIP_PDP_ENRICH=true)")

        print(f"✅ {len(page_products)} produits assemblés sur cette page")

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
    # Respecter un éventuel MAX_PRODUCTS global (par page cumulée)
    try:
        try:
            max_products_env = int(os.getenv("MAX_PRODUCTS", "0") or "0")
        except ValueError:
            max_products_env = 0

        for url in URLS_TO_SCRAPE:
            products_from_category = scrape_category_page(driver, wait, url)
            if max_products_env and len(all_products_data) + len(products_from_category) > max_products_env:
                take = max(0, max_products_env - len(all_products_data))
                all_products_data.extend(products_from_category[:take])
                print(f"✨ Limite MAX_PRODUCTS atteinte ({max_products_env}).")
                break
            else:
                all_products_data.extend(products_from_category)
                print(f"✨ {len(products_from_category)} produits ajoutés depuis cette catégorie.")
            if url != URLS_TO_SCRAPE[-1]: # Si ce n'est pas la dernière catégorie
                print(f"⏳ Pause de {DELAY_BETWEEN_PAGES} secondes avant la catégorie suivante...")
                time.sleep(DELAY_BETWEEN_PAGES)
    except Exception as e:
        print(f"❌ Erreur fatale pendant l'exécution: {e}")
        traceback.print_exc()
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    if all_products_data:
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(all_products_data, f, ensure_ascii=False, indent=4)
        print(f"\n🎯 Extraction terminée. {len(all_products_data)} produits au total enregistrés dans {OUTPUT_JSON}")

        if ENABLE_DB and _DB_IMPORT_OK and callable(save_to_database):
            print("\n💾 Tentative de sauvegarde en base de données...")
            try:
                save_to_database(OUTPUT_JSON, "serveurs", BRAND)
                print("✅ Sauvegarde en base de données réussie !")
            except Exception as e:
                print(f"❌ Erreur lors de la sauvegarde en base de données : {e}")
                print("💡 Assurez-vous que votre serveur MySQL est démarré et configuré correctement.")
        else:
            if not ENABLE_DB:
                print("ℹ️ Sauvegarde BD désactivée (ENABLE_DB=false)")
            elif not _DB_IMPORT_OK:
                print("ℹ️ Sauvegarde BD ignorée: import 'database.mysql_connector' introuvable.")
            else:
                print("ℹ️ Sauvegarde BD ignorée: fonction save_to_database non disponible.")
    else:
        print("\n⚠️ Aucun produit n'a été extrait. Le fichier JSON n'a pas été créé.")
