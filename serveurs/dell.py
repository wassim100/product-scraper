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
BASE_URLS = [
    # AI servers
    "https://www.dell.com/fr-fr/shop/serveurs-ia-poweredge/sf/poweredge-ai-servers?hve=explore+poweredge-ai-servers",
    # Datacenter servers
    "https://www.dell.com/fr-fr/shop/serveurs-de-datacenter/sf/poweredge-datacenter-servers?hve=explore+poweredge-datacenter-servers",
    # Edge servers
    "https://www.dell.com/fr-fr/shop/serveurs-de-p%C3%A9riph%C3%A9rie/sf/poweredge-edge-servers?hve=explore+poweredge-edge-servers",
    # Integrated rack scalable systems
    "https://www.dell.com/fr-fr/shop/dell-poweredge-integrated-rack-scalable-systems/sf/integrated-rack-scalable-systems?hve=explore+integrated-rack-scalable-systems"
]
BRAND = "Dell"
OUTPUT_JSON = "dell_servers_full.json"

# --- CONFIGURATION POUR LE TEST ---
DELAY_BETWEEN_TABS = 3
DELAY_BETWEEN_SOCKETS = 2
DELAY_BETWEEN_PRODUCTS = 1

# --- SETUP SELENIUM ---
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.mysql_connector import save_to_database
ENABLE_DB = os.getenv("ENABLE_DB", "false").lower() == "true"
MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "0") or "0")
FAST_SCRAPE = os.getenv("FAST_SCRAPE", "false").strip().lower() in {"1","true","yes","on"}

HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").strip().lower() in {"1","true","yes","on"}
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.page_load_strategy = 'eager'
options.add_argument("--ignore-certificate-errors")
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
if FAST_SCRAPE:
    options.add_argument("--blink-settings=imagesEnabled=false")
if HEADLESS_MODE:
    options.add_argument("--headless=new")
# Utiliser Selenium Manager (fallback local si présent)
try:
    driver = webdriver.Chrome(options=options)
except Exception:
    try:
        local_driver = os.path.join(os.getcwd(), "chromedriver.exe")
        driver = webdriver.Chrome(service=Service(local_driver), options=options)
    except Exception as e:
        raise e
driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
try:
    driver.set_page_load_timeout(15 if FAST_SCRAPE else 25)
except Exception:
    pass
wait = WebDriverWait(driver, 15 if FAST_SCRAPE else 20)
try:
    driver.implicitly_wait(0.5 if FAST_SCRAPE else 2)
except Exception:
    pass

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

        # Trouver tous les conteneurs de produits visibles (éviter les variantes masquées dds__d-none)
        product_containers = driver.find_elements(By.CSS_SELECTOR, ".cmfe-row[data-ff-id]:not(.dds__d-none)")
        if not product_containers:
            # Fallback: prendre toutes les lignes si le sélecteur de visibilité échoue
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
                    "h3", "h4", "h5",
                ]

                for selector in name_selectors:
                    try:
                        name_element = container.find_element(By.CSS_SELECTOR, selector)
                        name = name_element.text.strip()
                        if name:
                            break
                    except Exception:
                        continue

                # Si toujours pas de nom, essayer depuis l'attribut aria-label du lien
                if not name:
                    try:
                        link_element = container.find_element(By.CSS_SELECTOR, ".cmfe-shop-link")
                        aria_label = link_element.get_attribute("aria-label")
                        if aria_label and "Acheter dès maintenant" in aria_label:
                            name = aria_label.replace("Acheter dès maintenant des ", "").replace("Acheter dès maintenant de ", "")
                    except Exception:
                        pass

                # Extraire le lien du produit
                link_element = container.find_element(By.CSS_SELECTOR, ".cmfe-shop-link")
                link = link_element.get_attribute("href")

                # Extraire l'image
                image_url = None
                try:
                    image_element = container.find_element(By.CSS_SELECTOR, ".cmfe-variant-image")
                    image_url = image_element.get_attribute("src") or image_element.get_attribute("data-src")
                except Exception:
                    pass

                # Extraire le lien vers la datasheet
                datasheet_link = None
                try:
                    datasheet_element = container.find_element(By.CSS_SELECTOR, ".cmfe-spec-link")
                    datasheet_link = datasheet_element.get_attribute("href")
                except Exception:
                    pass

                # Amener la ligne en vue pour forcer le rendu lazy
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", container)
                    time.sleep(0.15 if FAST_SCRAPE else 0.2)
                except Exception:
                    pass

                # Extraire les spécifications directement depuis les cellules du tableau
                # On ignore la cellule prix mobile (masquée en desktop)
                cells = container.find_elements(
                    By.CSS_SELECTOR,
                    ".cmfe-col-inner:not(.dds__d-lg-none)"
                )
                # Fallbacks si moins de colonnes détectées
                if len(cells) < 5:
                    try:
                        cells = container.find_elements(
                            By.XPATH,
                            ".//div[@role='cell' and contains(@class,'cmfe-col-inner') and not(contains(@class,'dds__d-lg-none'))]"
                        )
                    except Exception:
                        pass
                if len(cells) < 5:
                    try:
                        raw_cells = container.find_elements(By.XPATH, "./div[@role='cell']")
                        filtered = []
                        for rc in raw_cells:
                            classes = (rc.get_attribute("class") or "")
                            if "cmfe-col-outer" in classes:
                                continue
                            if "dds__d-lg-none" in classes:
                                continue
                            filtered.append(rc)
                        if len(filtered) >= 5:
                            cells = filtered
                    except Exception:
                        pass

                tech_specs = {}

                spec_labels = [
                    # On saute la colonne "Charges applicatives" pour ne garder que des specs techniques
                    "Unités de rack",
                    "Processeur",
                    "Mémoire max",
                    "Espace de stockage max",
                    "Processeur graphique",
                ]

                # Normaliser et assigner par position
                # cells comprend encore la colonne description en première position
                # donc on commence à l'index 1
                for i, cell in enumerate(cells[1:]):
                    if i < len(spec_labels):
                        # Utiliser innerText pour capter le texte rendu
                        try:
                            text_raw = driver.execute_script("return arguments[0].innerText;", cell) or ""
                        except Exception:
                            text_raw = cell.text or ""
                        text_raw = text_raw.replace("\u00A0", " ")
                        spec_value = re.sub(r"\s+", " ", text_raw).strip()
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

                product_data = {
                    "brand": BRAND,
                    "link": link,
                    "name": name,
                    "tech_specs": tech_specs,
                    "scraped_at": datetime.now().isoformat(),
                    "datasheet_link": datasheet_link,
                    "image_url": [image_url] if image_url else [],
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

def extract_specs_from_product_page(driver, url: str) -> tuple[dict, dict]:
    """Ouvre la page produit et extrait des paires label→valeur depuis les blocs Spécifications.
    Robuste: tente plusieurs structures (dl/dt/dd, tables th/td, paires colonnes).
    """
    specs: dict[str, str] = {}
    assets: dict[str, object] = {"datasheet_link": None, "image_url": []}
    try:
        driver.get(url)
        # Attendre chargement
        try:
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            time.sleep(2)
        time.sleep(1)

        # Tenter de récupérer l'image principale (og:image ou image produit)
        try:
            og_img = driver.find_elements(By.CSS_SELECTOR, "meta[property='og:image']")
            if og_img:
                content = og_img[0].get_attribute("content")
                if content:
                    assets["image_url"].append(content)
        except Exception:
            pass
        try:
            hero_img = driver.find_elements(By.CSS_SELECTOR, "img[src*='poweredge'], img[alt*='PowerEdge']")
            for im in hero_img[:2]:
                src = im.get_attribute("src") or im.get_attribute("data-src")
                if src and src not in assets["image_url"]:
                    assets["image_url"].append(src)
        except Exception:
            pass

        # Tenter de récupérer un lien PDF de fiche technique
        try:
            pdf_links = driver.find_elements(By.CSS_SELECTOR, "a[href$='.pdf'], a[href*='spec-sheet'][href$='.pdf'], a[href*='specsheet'][href$='.pdf']")
            for a in pdf_links:
                href = a.get_attribute("href")
                if href and href.endswith('.pdf'):
                    assets["datasheet_link"] = href
                    break
        except Exception:
            pass

        # Chercher un conteneur de spécifications
        candidate_selectors = [
            "#specifications, section[id*='spec'], section[class*='spec'], div[id*='spec'], div[class*='spec']",
            "[data-testid*='spec'], [data-component*='spec']",
            ".dds__table, table",
            "dl"
        ]

        containers = []
        for sel in candidate_selectors:
            try:
                containers = driver.find_elements(By.CSS_SELECTOR, sel)
                if containers:
                    break
            except Exception:
                continue

        # Extraction depuis <dl>
        for c in containers:
            try:
                dts = c.find_elements(By.CSS_SELECTOR, "dt")
                dds = c.find_elements(By.CSS_SELECTOR, "dd")
                if dts and dds and len(dds) >= len(dts):
                    for i, dt in enumerate(dts):
                        key = dt.text.strip()
                        val = dds[i].text.strip() if i < len(dds) else ""
                        if key and val:
                            specs[key] = val
            except Exception:
                pass

        # Extraction depuis tables
        for c in containers:
            try:
                rows = c.find_elements(By.CSS_SELECTOR, "tr")
                for row in rows:
                    try:
                        th = row.find_elements(By.CSS_SELECTOR, "th, td")[0]
                        td = row.find_elements(By.CSS_SELECTOR, "th, td")[1]
                    except Exception:
                        continue
                    key = th.text.strip()
                    val = td.text.strip()
                    if key and val:
                        specs[key] = val
            except Exception:
                pass

        # Extraction générique paires colonnes (libellé/valeur)
        if not specs:
            try:
                items = driver.find_elements(By.CSS_SELECTOR, "[class*='spec'] [class*='label'], [class*='spec'] [class*='title']")
                for it in items:
                    try:
                        key = it.text.strip()
                        val_el = it.find_element(By.XPATH, "following-sibling::*[1]")
                        val = val_el.text.strip()
                        if key and val:
                            specs[key] = val
                    except Exception:
                        continue
            except Exception:
                pass

        # Fallback générique (li/p/div + strong|b|span[1])
        if not specs:
            try:
                pairs = driver.find_elements(By.XPATH, ".//*[self::li or self::p or self::div][./strong or ./b or ./span[1]]")
                for it in pairs:
                    try:
                        lbl = None
                        for sel in [".//strong[1]", ".//b[1]", ".//span[1]"]:
                            els = it.find_elements(By.XPATH, sel)
                            if els:
                                lbl = els[0]
                                break
                        if not lbl:
                            continue
                        k = lbl.text.strip()
                        v_full = (it.text or "").strip()
                        v = re.sub(r"^[\s:\-–—|]+", "", v_full.replace(k, "", 1)).strip()
                        if k and v:
                            specs[k] = v
                    except Exception:
                        continue
            except Exception:
                pass

    except Exception as e:
        print(f"⚠️ Erreur extraction détails page: {e}")

    # Nettoyage rapide: retirer très longues valeurs marketing
    cleaned = {}
    for k, v in specs.items():
        vs = re.sub(r"\s+", " ", v).strip()
        if vs and len(vs) <= 500:
            cleaned[k.strip()] = vs
    return cleaned, assets

def scrape_dell_servers():
    """Fonction principale pour scraper tous les serveurs Dell."""
    print(f"🚀 Démarrage du scraping Dell - {BRAND}")
    all_products = []

    # Parcourir toutes les pages de listing Dell demandées
    for url in BASE_URLS:
        try:
            print(f"🌐 Accès à la page : {url}")
            driver.get(url)

            # Gérer les cookies
            handle_cookie_banner(driver, wait)

            # Attendre que la page soit chargée
            time.sleep(2.5 if FAST_SCRAPE else 5)

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
                        time.sleep(1 if FAST_SCRAPE else DELAY_BETWEEN_TABS)

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
                                        time.sleep(0.8 if FAST_SCRAPE else DELAY_BETWEEN_SOCKETS)

                                    # Extraire les produits pour cette combinaison onglet/socket
                                    products = extract_products_from_current_page(driver)
                                    all_products.extend(products)
                                except Exception as e:
                                    print(f"❌ Erreur lors du traitement de l'option socket {socket_option['name']} : {e}")
                                    continue
                    except Exception as e:
                        print(f"❌ Erreur lors du traitement de l'onglet {tab['name']} : {e}")
                        continue
        except Exception as e:
            print(f"❌ Erreur lors du traitement de la page {url} : {e}")
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

    # Limite optionnelle pour les runs de test
    products_to_process = unique_products
    if MAX_PRODUCTS > 0:
        products_to_process = unique_products[:MAX_PRODUCTS]
        print(f"🔬 Limitation à {MAX_PRODUCTS} produits pour extraction détaillée")

    # Enrichir depuis la page produit
    enriched = []
    for idx, p in enumerate(products_to_process, 1):
        try:
            print(f"🔍 Détails {idx}/{len(products_to_process)}: {p['name']}")
            details, assets = extract_specs_from_product_page(driver, p['link'])
            if details:
                # Fusionner (conserver Socket existant)
                base_specs = p.get('tech_specs') or {}
                base_specs.update(details)
                p['tech_specs'] = base_specs
            # Remplacer/compléter assets depuis la page produit
            if assets.get('image_url'):
                p['image_url'] = assets['image_url']
            if assets.get('datasheet_link'):
                p['datasheet_link'] = assets['datasheet_link']
            enriched.append(p)
        except Exception as e:
            print(f"⚠️ Erreur enrichissement {p.get('name')}: {e}")
            enriched.append(p)

    return enriched

if __name__ == "__main__":
    try:
        products = scrape_dell_servers()
        
        if products:
            # Sauvegarder en JSON
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=4)
            print(f"💾 Données sauvegardées dans {OUTPUT_JSON}")
            
            # Sauvegarde en base de données
            if ENABLE_DB:
                print("💾 Tentative de sauvegarde en base de données...")
                try:
                    save_to_database(OUTPUT_JSON, "serveurs", BRAND)
                    print("✅ Sauvegarde en base de données réussie !")
                except Exception as e:
                    print(f"❌ Erreur lors de la sauvegarde en base de données : {e}")
            else:
                print("ℹ️ Sauvegarde BD désactivée (ENABLE_DB=false)")
        else:
            print("⚠️ Aucun produit n'a été extrait.")
            
    except Exception as e:
        print(f"❌ Erreur fatale : {e}")
    finally:
        driver.quit()
