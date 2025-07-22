import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options

# Configuration
OUTPUT_JSON = "lenovo_servers_full.json"
CATEGORIES = {
    "Rack Servers": "https://www.lenovo.com/tn/fr/c/servers-storage/servers/racks/",
    "Tower Servers": "https://www.lenovo.com/tn/fr/c/servers-storage/servers/towers/",
    "Edge Servers": "https://www.lenovo.com/tn/fr/c/servers-storage/servers/edge/",
    "Mission-Critical Servers": "https://www.lenovo.com/tn/fr/c/servers-storage/servers/mission-critical/",
    "Supercomputing Servers": "https://www.lenovo.com/tn/fr/c/servers-storage/servers/supercomputing/",
    "Multi-Node Servers": "https://www.lenovo.com/tn/fr/c/servers-storage/servers/multi-node/"
}

def setup_driver():
    """Configure et retourne le driver Chrome"""
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def handle_cookie_banner(driver):
    """Gère les bannières de cookies"""
    try:
        # Attendre et accepter les cookies si présents
        cookie_selectors = [
            "button[id*='cookie']",
            "button[class*='cookie']",
            "button[id*='accept']",
            "button[class*='accept']",
            "#onetrust-accept-btn-handler",
            ".cookie-accept-btn",
            "[data-testid='cookie-accept']"
        ]
        
        for selector in cookie_selectors:
            try:
                cookie_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                cookie_button.click()
                print("✅ Bannière de cookies fermée")
                time.sleep(1)
                return True
            except TimeoutException:
                continue
        
        return False
    except Exception as e:
        print(f"⚠️ Erreur lors de la gestion des cookies : {e}")
        return False

def extract_product_specs(product_element):
    """Extrait les spécifications techniques d'un produit depuis la page de liste"""
    specs = {}
    
    try:
        # Chercher les spécifications dans la structure HTML de Lenovo
        # Nouvelle structure basée sur votre HTML : .features div
        features_section = product_element.find_element(By.CSS_SELECTOR, ".features div")
        if features_section:
            # Extraire les spécifications depuis les balises <ul><li> avec <strong>
            spec_items = features_section.find_elements(By.CSS_SELECTOR, "li")
            for spec_item in spec_items:
                try:
                    spec_html = spec_item.get_attribute("innerHTML")
                    # Parser le HTML pour extraire les spécifications
                    if "<strong>" in spec_html and ":</strong>" in spec_html:
                        # Format: <strong>Key:</strong> Value
                        parts = spec_html.split(":</strong>", 1)
                        if len(parts) == 2:
                            key = parts[0].replace("<strong>", "").replace("<p>", "").strip()
                            value = parts[1].replace("</p>", "").replace("</li>", "").strip()
                            # Nettoyer les balises HTML restantes
                            import re
                            value = re.sub(r'<[^>]+>', '', value).strip()
                            if key and value:
                                specs[key] = value
                    else:
                        # Fallback : essayer avec le texte brut
                        spec_text = spec_item.text.strip()
                        if spec_text and ":" in spec_text:
                            key, value = spec_text.split(":", 1)
                            specs[key.strip()] = value.strip()
                except Exception as e:
                    continue
        
        # Fallback : si pas de spécifications dans .features div, essayer le texte direct
        if not specs:
            try:
                features_text = product_element.find_element(By.CSS_SELECTOR, ".features div").text.strip()
                if features_text and len(features_text) > 10:  # Description générale
                    specs["Description"] = features_text
            except:
                pass
                    
    except NoSuchElementException:
        # Fallback vers les anciens sélecteurs si la nouvelle structure n'est pas trouvée
        try:
            spec_sections = product_element.find_elements(By.CSS_SELECTOR, "ul li, .product-specs li, .spec-item")
            for spec in spec_sections:
                try:
                    spec_text = spec.text.strip()
                    if spec_text and ":" in spec_text:
                        key, value = spec_text.split(":", 1)
                        specs[key.strip()] = value.strip()
                    elif spec_text:
                        specs[spec_text] = ""
                except Exception:
                    continue
        except Exception as e:
            print(f"⚠️ Erreur lors de l'extraction des spécifications : {e}")
    
    return specs

def extract_detailed_specs_from_product_page(driver, product_link):
    """Extrait les spécifications techniques détaillées depuis la page produit individuelle"""
    specs = {}
    datasheet_link = ""
    
    try:
        print(f"🔍 Extraction des spécifications depuis : {product_link}")
        
        # Ouvrir la page produit dans un nouvel onglet
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        
        try:
            driver.get(product_link)
            time.sleep(5)  # Attendre plus longtemps pour le chargement JavaScript
            
            # Débogage : afficher le titre de la page
            page_title = driver.title
            print(f"📄 Page chargée : {page_title}")
            
            # Essayer de cliquer sur l'onglet "Tech Specs"
            try:
                tech_specs_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Tech Specs') or contains(text(), 'Spécifications') or contains(text(), 'Specifications')]")
                if tech_specs_tab.is_displayed():
                    tech_specs_tab.click()
                    print("✅ Clic sur l'onglet 'Tech Specs'")
                    time.sleep(3)  # Attendre le chargement des spécifications
            except:
                print("⚠️ Onglet 'Tech Specs' non trouvé ou déjà ouvert")
            
            # Chercher les spécifications dans la structure HTML identifiée
            try:
                # Chercher le conteneur des spécifications
                specs_container = driver.find_element(By.CSS_SELECTOR, ".specs-table")
                if specs_container:
                    print("✅ Conteneur des spécifications trouvé")
                    
                    # Extraire chaque item de spécification
                    spec_items = specs_container.find_elements(By.CSS_SELECTOR, ".item")
                    print(f"🔍 Trouvé {len(spec_items)} items de spécifications")
                    
                    for item in spec_items:
                        try:
                            # Extraire la clé (titre de la spécification)
                            key_element = item.find_element(By.CSS_SELECTOR, ".specs-table-th .spec-title")
                            key = key_element.text.strip()
                            
                            # Extraire la valeur (contenu de la spécification)
                            value_element = item.find_element(By.CSS_SELECTOR, ".specs-table-td.spec_text")
                            value = value_element.text.strip()
                            
                            # Nettoyer la valeur (supprimer les sauts de ligne multiples)
                            value = ' '.join(value.split())
                            
                            if key and value:
                                specs[key] = value
                                
                                # Vérifier si c'est le lien vers la datasheet
                                if key.lower() == "datasheet":
                                    try:
                                        datasheet_link_element = value_element.find_element(By.CSS_SELECTOR, "a")
                                        datasheet_href = datasheet_link_element.get_attribute("href")
                                        if datasheet_href:
                                            datasheet_link = datasheet_href
                                            print(f"📄 Lien datasheet trouvé: {datasheet_link}")
                                    except:
                                        pass
                                        
                        except Exception as e:
                            print(f"⚠️ Erreur lors de l'extraction d'un item: {e}")
                            continue
                            
                    print(f"✅ {len(specs)} spécifications extraites avec succès")
                    
            except Exception as e:
                print(f"⚠️ Erreur lors de l'extraction des spécifications: {e}")
                
                # Fallback : essayer avec d'autres sélecteurs
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
                                        specs[key] = ' '.join(value.split())
                                        
                                except Exception:
                                    continue
                            
                            if specs:
                                break
                                
                    except Exception:
                        continue
            
            # Chercher d'autres liens PDF si datasheet_link n'est pas trouvé
            if not datasheet_link:
                datasheet_selectors = [
                    "a[href*='lenovopress.com']",
                    "a[href*='.pdf']",
                    "a[href*='datasheet']",
                    "a[href*='spec']",
                    "a[href*='ds0']"  # Format spécifique Lenovo (ds0150)
                ]
                
                for selector in datasheet_selectors:
                    try:
                        datasheet_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in datasheet_elements:
                            href = element.get_attribute("href")
                            if href and ("lenovopress.com" in href or ".pdf" in href.lower()):
                                datasheet_link = href
                                break
                        if datasheet_link:
                            break
                    except Exception:
                        continue
            
            print(f"✅ Spécifications extraites: {len(specs)} éléments")
            if datasheet_link:
                print(f"📄 Datasheet trouvé: {datasheet_link}")
            
            # Afficher quelques spécifications pour le débogage
            if specs:
                print("🔍 Exemples de spécifications:")
                for i, (key, value) in enumerate(list(specs.items())[:3]):
                    print(f"  - {key}: {value[:100]}...")
            
        except Exception as e:
            print(f"⚠️ Erreur lors de l'extraction des spécifications: {e}")
        
        finally:
            # Fermer l'onglet et revenir à l'onglet principal
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            
    except Exception as e:
        print(f"❌ Erreur lors de l'ouverture de la page produit: {e}")
    
    return specs, datasheet_link

def extract_products_from_page(driver, category_name):
    """Extrait tous les produits d'une page de catégorie"""
    products = []
    
    print("🔄 Chargement des produits avec scroll et boutons 'Load More'...")
    
    try:
        # Attendre que la page se charge complètement
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.product_item, .product_item"))
        )
        
        # Compter les produits initiaux
        initial_products = len(driver.find_elements(By.CSS_SELECTOR, "li.product_item"))
        print(f"📊 Produits initiaux détectés: {initial_products}")
        
        # Scroll progressif pour déclencher le lazy loading
        print("🔄 Scroll progressif pour déclencher le lazy loading...")
        
        scroll_increment = 200
        current_position = 0
        max_scrolls = 25
        
        for i in range(max_scrolls):
            current_position += scroll_increment
            driver.execute_script(f"window.scrollTo(0, {current_position});")
            time.sleep(3)  # Attendre 3 secondes à chaque scroll
            
            current_products = len(driver.find_elements(By.CSS_SELECTOR, "li.product_item"))
            
            if i % 5 == 0:  # Afficher le progrès tous les 5 scrolls
                print(f"📜 Scroll {i+1}/{max_scrolls} - Position: {current_position}px - Produits: {current_products}")
        
        # Scroll final vers le bas
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)
        
        products_after_scroll = len(driver.find_elements(By.CSS_SELECTOR, "li.product_item"))
        print(f"📊 Produits après scroll: {products_after_scroll}")
        
        # Gérer la popup qui peut apparaître après le scroll
        print("🔍 Vérification des popups après scroll...")
        try:
            # Chercher spécifiquement la popup eBook
            popup_indicators = [
                "//*[contains(text(), 'Getting started with AI')]",
                "//*[contains(text(), 'eBook')]",
                "//*[contains(text(), 'LIRE L')]"
            ]
            
            popup_detected = False
            for indicator in popup_indicators:
                try:
                    elements = driver.find_elements(By.XPATH, indicator)
                    if elements:
                        popup_detected = True
                        print(f"✅ Popup détectée: {indicator}")
                        break
                except:
                    continue
            
            if popup_detected:
                print("🔄 Fermeture de la popup eBook...")
                
                # Chercher le bouton de fermeture
                close_selectors = [
                    "button[class*='close']",
                    "button[aria-label*='close']",
                    ".close",
                    "[data-dismiss]",
                    "button[title*='close']",
                    "svg[class*='close']"
                ]
                
                popup_closed = False
                for selector in close_selectors:
                    try:
                        close_button = driver.find_element(By.CSS_SELECTOR, selector)
                        if close_button.is_displayed():
                            close_button.click()
                            time.sleep(3)
                            popup_closed = True
                            print("✅ Popup fermée avec succès")
                            break
                    except:
                        continue
                
                # Si pas de bouton trouvé, essayer Escape
                if not popup_closed:
                    try:
                        from selenium.webdriver.common.keys import Keys
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        time.sleep(3)
                        print("⌨️ Escape envoyé pour fermer la popup")
                    except:
                        pass
            else:
                print("✅ Aucune popup détectée après le scroll")
                
        except Exception as e:
            print(f"⚠️ Erreur lors de la gestion de la popup: {e}")
        
        # Attendre que la popup soit complètement fermée
        time.sleep(3)
        
        # Chercher et cliquer sur le bouton "Load More"
        print("🔍 Recherche du bouton 'Load More'...")
        
        load_more_found = False
        
        # Recherche spécifique du bouton "Load more results"
        try:
            all_buttons = driver.find_elements(By.CSS_SELECTOR, "button, a")
            
            for button in all_buttons:
                try:
                    if button.is_displayed() and button.is_enabled():
                        button_text = button.text.strip().lower()
                        
                        # Chercher spécifiquement "Load more results" et exclure "Learn More"
                        if ("load more results" in button_text or 
                            "voir plus de résultats" in button_text or
                            "afficher plus de résultats" in button_text) and "learn" not in button_text:
                            
                            print(f"✅ Bouton 'Load More' trouvé: '{button.text.strip()}'")
                            
                            # Scroll vers le bouton
                            driver.execute_script("arguments[0].scrollIntoView(true);", button)
                            time.sleep(3)
                            
                            # Compter les produits avant le clic
                            products_before = len(driver.find_elements(By.CSS_SELECTOR, "li.product_item"))
                            print(f"📊 Produits avant clic: {products_before}")
                            
                            # Cliquer sur le bouton avec JavaScript pour plus de fiabilité
                            driver.execute_script("arguments[0].click();", button)
                            print("🖱️ Clic JavaScript sur le bouton 'Load More' réussi")
                            
                            # Attendre le chargement avec un timeout plus long
                            print("⏳ Attente du chargement des nouveaux produits...")
                            time.sleep(15)
                            
                            # Compter les produits après le clic
                            products_after = len(driver.find_elements(By.CSS_SELECTOR, "li.product_item"))
                            print(f"📊 Produits après clic: {products_after}")
                            
                            if products_after > products_before:
                                print(f"🎉 Succès! {products_after - products_before} nouveaux produits chargés")
                                load_more_found = True
                                
                                # Essayer de cliquer à nouveau s'il y a encore un bouton
                                for attempt in range(2):
                                    try:
                                        # Chercher à nouveau le bouton
                                        more_buttons = driver.find_elements(By.CSS_SELECTOR, "button, a")
                                        for new_button in more_buttons:
                                            if (new_button.is_displayed() and new_button.is_enabled() and
                                                "load more results" in new_button.text.strip().lower() and 
                                                "learn" not in new_button.text.strip().lower()):
                                                
                                                print(f"🔄 Nouveau bouton 'Load More' trouvé")
                                                
                                                current_count = len(driver.find_elements(By.CSS_SELECTOR, "li.product_item"))
                                                driver.execute_script("arguments[0].scrollIntoView(true);", new_button)
                                                time.sleep(2)
                                                driver.execute_script("arguments[0].click();", new_button)
                                                time.sleep(15)
                                                
                                                new_count = len(driver.find_elements(By.CSS_SELECTOR, "li.product_item"))
                                                if new_count > current_count:
                                                    print(f"🎉 {new_count - current_count} nouveaux produits chargés!")
                                                    break
                                                else:
                                                    print("⚠️ Pas de nouveaux produits")
                                                    
                                    except Exception:
                                        break
                                
                                break
                            else:
                                print("⚠️ Pas de nouveaux produits après le clic")
                                
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"⚠️ Erreur lors de la recherche du bouton 'Load More': {e}")
        
        if not load_more_found:
            print("⚠️ Aucun bouton 'Load More' trouvé ou utilisable")
        
        # Compter les produits finaux
        final_products = len(driver.find_elements(By.CSS_SELECTOR, "li.product_item"))
        print(f"🎯 Nombre final de produits: {final_products}")
        
        # Maintenant extraire tous les produits
        product_elements = driver.find_elements(By.CSS_SELECTOR, "li.product_item")
        
        if not product_elements:
            print("❌ Aucun produit trouvé sur cette page")
            return products
        
        print(f"🔍 Extraction de {len(product_elements)} produits avec spécifications détaillées...")
        
        for i, product in enumerate(product_elements, 1):
            try:
                # Extraire le nom du produit
                name = ""
                name_selectors = [
                    ".product_title a",
                    ".product_title",
                    "a[id*='title_']",
                    "h3", "h4", "h5",
                    ".product-name", ".product-title",
                    "[class*='title']"
                ]
                
                for selector in name_selectors:
                    try:
                        name_element = product.find_element(By.CSS_SELECTOR, selector)
                        name = name_element.text.strip()
                        if name:
                            break
                    except NoSuchElementException:
                        continue
                
                if not name:
                    print(f"⚠️ Nom du produit {i} non trouvé")
                    continue
                
                # Extraire le lien
                link = ""
                try:
                    link_element = product.find_element(By.CSS_SELECTOR, ".product_title a, a[id*='title_'], .lazy_href")
                    link = link_element.get_attribute("href")
                    if link and not link.startswith("http"):
                        link = "https://www.lenovo.com" + link
                except NoSuchElementException:
                    # Essayer avec data-dlp-url
                    try:
                        link = product.get_attribute("data-dlp-url")
                        if link and not link.startswith("http"):
                            link = "https://www.lenovo.com" + link
                    except:
                        print(f"⚠️ Lien du produit {name} non trouvé")
                
                # Extraire l'image
                image_url = ""
                try:
                    img_element = product.find_element(By.CSS_SELECTOR, ".normal_image img, .image_focus")
                    image_url = img_element.get_attribute("src")
                    if image_url and not image_url.startswith("http"):
                        if image_url.startswith("//"):
                            image_url = "https:" + image_url
                        else:
                            image_url = "https://www.lenovo.com" + image_url
                except NoSuchElementException:
                    print(f"⚠️ Image du produit {name} non trouvée")
                
                # Extraire les spécifications depuis la page de liste (rapide)
                specs_preview = extract_product_specs(product)
                
                # Extraire les spécifications détaillées depuis la page produit individuelle
                detailed_specs = {}
                datasheet_link = ""
                
                if link:  # Seulement si on a un lien vers la page produit
                    try:
                        detailed_specs, datasheet_link = extract_detailed_specs_from_product_page(driver, link)
                        
                        # Combiner les spécifications (détaillées prioritaires)
                        combined_specs = {}
                        combined_specs.update(specs_preview)  # Ajouter les spécifications de la page de liste
                        combined_specs.update(detailed_specs)  # Ajouter les spécifications détaillées (écrasent les précédentes)
                        
                        specs = combined_specs
                        
                    except Exception as e:
                        print(f"⚠️ Erreur lors de l'extraction détaillée pour {name}: {e}")
                        specs = specs_preview  # Fallback vers les spécifications de la page de liste
                else:
                    specs = specs_preview
                
                # Créer l'objet produit
                product_data = {
                    "brand": "Lenovo",
                    "category": category_name,
                    "name": name,
                    "link": link,
                    "image_url": image_url,
                    "tech_specs": specs,
                    "scraped_at": datetime.now().isoformat(),
                    "datasheet_link": datasheet_link
                }
                
                products.append(product_data)
                print(f"✅ Produit {i} extrait: {name}")
                
            except Exception as e:
                print(f"❌ Erreur lors de l'extraction du produit {i}: {e}")
                continue
        
        print(f"✅ {len(products)} produits extraits de la catégorie {category_name}")
        
    except TimeoutException:
        print(f"❌ Timeout lors de l'attente des produits pour {category_name}")
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction des produits de {category_name}: {e}")
    
    return products

def scrape_lenovo_servers():
    """Fonction principale pour scraper tous les serveurs Lenovo"""
    driver = setup_driver()
    all_products = []
    
    try:
        for category_name, url in CATEGORIES.items():
            print(f"\n🔍 Scraping de la catégorie: {category_name}")
            print(f"URL: {url}")
            
            try:
                driver.get(url)
                time.sleep(3)
                
                # Gérer les cookies à la première visite
                if category_name == list(CATEGORIES.keys())[0]:
                    handle_cookie_banner(driver)
                    time.sleep(2)
                
                # Gérer la popup eBook si elle apparaît
                print("🔍 Gestion des popups...")
                try:
                    # Chercher spécifiquement la popup eBook
                    popup_indicators = [
                        "//*[contains(text(), 'Getting started with AI')]",
                        "//*[contains(text(), 'eBook')]",
                        "//*[contains(text(), 'LIRE L')]"
                    ]
                    
                    popup_detected = False
                    for indicator in popup_indicators:
                        try:
                            elements = driver.find_elements(By.XPATH, indicator)
                            if elements:
                                popup_detected = True
                                break
                        except:
                            continue
                    
                    if popup_detected:
                        print("🔄 Popup eBook détectée, tentative de fermeture...")
                        
                        # Chercher le bouton de fermeture
                        close_selectors = [
                            "button[class*='close']",
                            "button[aria-label*='close']",
                            ".close",
                            "[data-dismiss]"
                        ]
                        
                        popup_closed = False
                        for selector in close_selectors:
                            try:
                                close_button = driver.find_element(By.CSS_SELECTOR, selector)
                                if close_button.is_displayed():
                                    close_button.click()
                                    time.sleep(2)
                                    popup_closed = True
                                    print("✅ Popup fermée")
                                    break
                            except:
                                continue
                        
                        # Si pas de bouton trouvé, essayer Escape
                        if not popup_closed:
                            try:
                                from selenium.webdriver.common.keys import Keys
                                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                                time.sleep(2)
                                print("⌨️ Escape envoyé")
                            except:
                                pass
                    else:
                        print("✅ Aucune popup détectée")
                        
                except Exception as e:
                    print(f"⚠️ Erreur popup: {e}")
                
                time.sleep(2)
                
                # Extraire les produits de cette catégorie
                products = extract_products_from_page(driver, category_name)
                all_products.extend(products)
                
                # Pause entre les catégories
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ Erreur lors du scraping de {category_name}: {e}")
                continue
        
        # Sauvegarder les données
        print(f"\n💾 Sauvegarde de {len(all_products)} produits...")
        
        # Déduplication basée sur le nom et le lien
        seen = set()
        unique_products = []
        
        for product in all_products:
            identifier = (product.get("name", ""), product.get("link", ""))
            if identifier not in seen and identifier != ("", ""):
                seen.add(identifier)
                unique_products.append(product)
        
        print(f"🔄 Après déduplication: {len(unique_products)} produits uniques")
        
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(unique_products, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Scraping terminé ! {len(unique_products)} produits sauvegardés dans {OUTPUT_JSON}")
        
        # Statistiques par catégorie
        print("\n📊 Statistiques par catégorie:")
        for category in CATEGORIES.keys():
            count = len([p for p in unique_products if p.get("category") == category])
            print(f"  - {category}: {count} produits")
        
    except Exception as e:
        print(f"❌ Erreur générale : {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_lenovo_servers()
