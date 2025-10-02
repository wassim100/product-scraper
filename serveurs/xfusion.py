"""
Scraper XFusion amélioré pour extraire tous les modèles de serveurs
"""

import time
import json
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import os
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XFusionServerScraperImproved:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.logger = logger
        
        # URLs des différentes catégories
        self.categories = {
            "Rack Servers": "https://www.xfusion.com/en/product/rack-server",
            "High-Density Servers": "https://www.xfusion.com/en/product/high-density-server", 
            "AI Servers": "https://www.xfusion.com/en/product/heterogeneous-server",
            "Rack-Scale Servers": "https://www.xfusion.com/en/product/rack-scale-servers/fusionserver-fusionpod",
            "FusionPoD for AI": "https://www.xfusion.com/en/product/rack-scale-servers/fusionpod-for-ai"
        }
    
    def setup_driver(self):
        """Configuration du driver Chrome"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # Utiliser Selenium Manager; fallback local si nécessaire
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except Exception:
            local_driver = os.path.join(os.getcwd(), "chromedriver.exe")
            self.driver = webdriver.Chrome(service=Service(local_driver), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 15)
        
    def extract_table_servers_improved(self, url, category_name):
        """Extrait tous les serveurs d'une catégorie avec scroll infini"""
        servers = []
        
        try:
            self.driver.get(url)
            time.sleep(5)
            
            # Attendre le chargement complet
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Gérer le scroll infini pour charger tous les éléments
            self.logger.info(f"🔄 Gestion du scroll infini pour {category_name}...")
            
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while scroll_attempts < max_scroll_attempts:
                # Scroll vers le bas
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # Attendre le chargement des nouveaux éléments
                time.sleep(3)
                
                # Calculer la nouvelle hauteur
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                
                # Si la hauteur n'a pas changé, on a atteint la fin
                if new_height == last_height:
                    self.logger.info(f"✅ Fin du scroll atteinte après {scroll_attempts} tentatives")
                    break
                    
                last_height = new_height
                scroll_attempts += 1
                self.logger.info(f"📜 Scroll {scroll_attempts}: nouvelle hauteur = {new_height}")
            
            # Attendre un peu plus pour le chargement final
            time.sleep(5)
            
            # Chercher le tableau après le scroll complet
            table_found = False
            
            # Méthode 1: Chercher par classe ivu-table
            try:
                table_element = self.driver.find_element(By.CLASS_NAME, "ivu-table")
                table_found = True
                self.logger.info(f"✅ Tableau trouvé avec ivu-table pour {category_name}")
            except:
                pass
            
            # Méthode 2: Chercher directement les lignes
            if not table_found:
                try:
                    rows = self.driver.find_elements(By.CSS_SELECTOR, "tbody tr")
                    if rows:
                        table_found = True
                        self.logger.info(f"✅ Lignes trouvées directement pour {category_name}")
                except:
                    pass
            
            if not table_found:
                self.logger.warning(f"❌ Aucun tableau trouvé pour {category_name}")
                return servers
                
            # Extraire toutes les lignes du tableau (après scroll complet)
            row_selectors = [
                "tbody.ivu-table-tbody tr",
                ".ivu-table-tbody tr", 
                "tbody tr"
            ]
            
            rows = []
            for selector in row_selectors:
                try:
                    found_rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if found_rows:
                        rows = found_rows
                        self.logger.info(f"🔍 Trouvé {len(rows)} lignes avec: {selector}")
                        break
                except:
                    continue
            
            self.logger.info(f"📊 Total lignes trouvées: {len(rows)}")
            
            # Extraire les données de chaque ligne
            for i, row in enumerate(rows):
                try:
                    server_data = self.extract_server_from_row(row, category_name)
                    if server_data:
                        servers.append(server_data)
                        self.logger.info(f"✅ Serveur {i+1}: {server_data['name']}")
                        
                except Exception as e:
                    self.logger.debug(f"Erreur ligne {i+1}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Erreur lors du scraping {category_name}: {e}")
            
        return servers
    
    def extract_server_from_row(self, row, category):
        """Extrait les données d'un serveur depuis une ligne de tableau"""
        try:
            # Chercher les cellules TD
            cells = row.find_elements(By.TAG_NAME, "td")
            
            if len(cells) < 2:  # Au minimum la cellule Model
                return None
            
            # Gestion des rowspan - la structure peut varier
            name_cell = None
            processor_cell = None
            accelerator_cell = None
            memory_cell = None
            storage_cell = None
            scenarios_cell = None
            
            # Identifier la cellule contenant le nom du serveur
            for i, cell in enumerate(cells):
                cell_text = cell.text.strip()
                if "FusionServer" in cell_text or "KunLun" in cell_text:
                    name_cell = cell
                    name = cell_text
                    
                    # Déterminer l'index de départ selon la structure
                    if len(cells) == 6:  # Ligne complète avec scenarios
                        scenarios_cell = cells[0]
                        processor_cell = cells[i+1] if i+1 < len(cells) else None
                        accelerator_cell = cells[i+2] if i+2 < len(cells) else None
                        memory_cell = cells[i+3] if i+3 < len(cells) else None
                        storage_cell = cells[i+4] if i+4 < len(cells) else None
                    elif len(cells) == 5:  # Ligne sans scenarios (rowspan)
                        processor_cell = cells[i+1] if i+1 < len(cells) else None
                        accelerator_cell = cells[i+2] if i+2 < len(cells) else None
                        memory_cell = cells[i+3] if i+3 < len(cells) else None
                        storage_cell = cells[i+4] if i+4 < len(cells) else None
                    break
            
            if not name_cell or not name:
                return None
                
            # Extraire les données
            scenarios = scenarios_cell.text.strip() if scenarios_cell else ""
            processor = processor_cell.text.strip() if processor_cell else ""
            accelerator = accelerator_cell.text.strip() if accelerator_cell else ""
            memory = memory_cell.text.strip() if memory_cell else ""
            storage = storage_cell.text.strip() if storage_cell else ""
            
            # Nettoyer le nom
            name = name.replace('\n', ' ').replace('\r', ' ').strip()
            
            # Extraire le lien "View" si disponible
            link = ""
            try:
                # Chercher le lien dans la dernière cellule ou dans toutes les cellules
                for cell in cells:
                    view_links = cell.find_elements(By.CSS_SELECTOR, "a.view")
                    if view_links:
                        link = view_links[0].get_attribute("href")
                        if link.startswith("/"):
                            link = "https://www.xfusion.com" + link
                        break
            except:
                pass
            
            if not link:
                # Construire l'URL du produit
                name_clean = name.lower().replace(' ', '-').replace('®', '').replace('™', '')
                category_url = category.lower().replace(' ', '-').replace('-servers', '-server')
                link = f"https://www.xfusion.com/en/product/{category_url}/{name_clean}"
            
            server_data = {
                "brand": "XFusion",
                "category": category,
                "name": name,
                "link": link,
                "tech_specs": {
                    "Main Application Scenarios": scenarios,
                    "Processor" if category != "AI Servers" else "Node/Processors": processor,
                    "Accelerator Card": accelerator,
                    "DIMM": memory,
                    "Storage": storage
                },
                "scraped_at": datetime.now().isoformat(),
                "datasheet_link": "",
                "image_url": ""
            }
            
            # Extraire les liens datasheet, image et spécifications détaillées depuis la page produit
            datasheet_link, image_url, detailed_specs = self.extract_product_details(link)
            server_data["datasheet_link"] = datasheet_link
            server_data["image_url"] = image_url
            
            # Remplacer les spécifications basiques par les détaillées si disponibles
            if detailed_specs:
                server_data["tech_specs"] = detailed_specs
                self.logger.info(f"✅ Spécifications détaillées remplacées pour: {name}")
            
            # Filtrer les chassis et nodes - ne garder que les serveurs complets
            if not self.is_complete_server(server_data):
                return None  # Exclure ce produit
            
            return server_data
                
        except Exception as e:
            self.logger.debug(f"Erreur extraction serveur: {e}")
            return None
    
    def is_complete_server(self, server_data):
        """Vérifie si le produit est un serveur complet (pas un chassis ou node)"""
        if not server_data:
            return False
            
        name = server_data.get("name", "").lower()
        
        # Mots-clés qui indiquent que c'est un chassis ou node (pas un serveur complet)
        exclusion_keywords = [
            "chassis",
            "node", 
            "half-width node",
            "full-width node",
            "compute node",
            "heterogeneous compute node"
        ]
        
        # Vérifier si le nom contient des mots-clés d'exclusion
        for keyword in exclusion_keywords:
            if keyword in name:
                self.logger.info(f"🚫 Produit filtré (chassis/node): {server_data['name']}")
                return False
        
        # Vérifier aussi dans les spécifications techniques
        tech_specs = server_data.get("tech_specs", {})
        for key, value in tech_specs.items():
            value_lower = str(value).lower()
            if any(keyword in value_lower for keyword in ["chassis", "compute node", "heterogeneous compute node"]):
                self.logger.info(f"🚫 Produit filtré (détecté dans specs): {server_data['name']}")
                return False
        
        # Si aucun mot-clé d'exclusion trouvé, c'est probablement un serveur complet
        self.logger.info(f"✅ Serveur complet validé: {server_data['name']}")
        return True
    
    def extract_product_details(self, product_url):
        """Extrait les détails complets depuis la page produit individuelle"""
        datasheet_link = ""
        image_url = ""
        detailed_specs = {}
        
        try:
            # Ouvrir un nouvel onglet pour la page produit
            self.driver.execute_script("window.open('');")
            self.driver.switch_to.window(self.driver.window_handles[1])
            
            self.driver.get(product_url)
            time.sleep(5)
            
            # ÉTAPE 1: Extraire les spécifications techniques détaillées
            self.logger.info(f"🔍 Extraction des spécifications techniques pour: {product_url}")
            
            # Cliquer sur l'onglet "Technical Specifications" en premier
            try:
                tech_specs_tab = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Technical Specifications')]")
                self.driver.execute_script("arguments[0].click();", tech_specs_tab)
                time.sleep(3)
                self.logger.debug("✅ Clic sur l'onglet Technical Specifications")
            except:
                self.logger.debug("ℹ️ Onglet Technical Specifications non trouvé ou déjà ouvert")
            
            # Extraire le tableau des spécifications techniques
            try:
                # Méthode 1: Chercher le tableau principal des specs
                spec_tables = self.driver.find_elements(By.XPATH, "//table[.//th[contains(text(), 'Parameter')] or .//th[contains(text(), 'Description')]]")
                
                if spec_tables:
                    table = spec_tables[0]
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    
                    for row in rows[1:]:  # Skip header row
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 2:
                            param = cells[0].text.strip()
                            description = cells[1].text.strip()
                            
                            if param and description and param != "Parameter":
                                detailed_specs[param] = description
                    
                    self.logger.info(f"✅ {len(detailed_specs)} spécifications extraites du tableau")
                
                # Méthode 2: Chercher d'autres structures de spécifications
                if not detailed_specs:
                    # Chercher des divs ou autres éléments avec des spécifications
                    spec_items = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'spec') or contains(@class, 'parameter')]")
                    
                    for item in spec_items:
                        text = item.text.strip()
                        if ":" in text:
                            parts = text.split(":", 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                value = parts[1].strip()
                                detailed_specs[key] = value
                
                # Méthode 3: Si aucune spec trouvée, utiliser les données basiques de la page
                if not detailed_specs:
                    self.logger.debug("⚠️ Aucune spécification détaillée trouvée, extraction des données visibles")
                    
                    # Extraire des informations visibles sur la page
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    
                    # Chercher des patterns communs
                    if "Form Factor" in page_text:
                        detailed_specs["Form Factor"] = "Information disponible sur la page"
                    if "Processor" in page_text:
                        detailed_specs["Processor"] = "Information disponible sur la page"
                
            except Exception as e:
                self.logger.debug(f"Erreur extraction spécifications: {e}")
            
            # ÉTAPE 2: Cliquer sur l'onglet "Related Resources" pour les datasheets
            try:
                related_tab = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Related Resources')]")
                self.driver.execute_script("arguments[0].click();", related_tab)
                time.sleep(2)
                self.logger.debug("✅ Clic sur l'onglet Related Resources")
            except:
                self.logger.debug("❌ Onglet Related Resources non trouvé")
            
            # ÉTAPE 3: Extraire le lien datasheet
            try:
                # Méthode 1: Chercher le lien avec texte "Datasheet"
                datasheet_elements = self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Datasheet')]")
                if datasheet_elements:
                    datasheet_link = datasheet_elements[0].get_attribute('href')
                    self.logger.info(f"✅ Datasheet trouvé: {datasheet_link}")
                else:
                    # Méthode 2: Chercher span avec texte "Datasheet" dans un lien parent
                    span_elements = self.driver.find_elements(By.XPATH, "//span[text()='Datasheet']")
                    for span in span_elements:
                        # Remonter pour trouver le lien parent
                        current = span
                        for _ in range(5):  # Remonter jusqu'à 5 niveaux
                            if current.tag_name == 'a':
                                datasheet_link = current.get_attribute('href')
                                self.logger.info(f"✅ Datasheet trouvé (méthode 2): {datasheet_link}")
                                break
                            try:
                                current = current.find_element(By.XPATH, "..")
                            except:
                                break
                        if datasheet_link:
                            break
                
                # Méthode 3: Chercher tous les liens et filtrer par href contenant "datasheet"
                if not datasheet_link:
                    all_links = self.driver.find_elements(By.TAG_NAME, "a")
                    for link in all_links:
                        href = link.get_attribute('href')
                        if href and 'datasheet' in href.lower():
                            datasheet_link = href
                            self.logger.info(f"✅ Datasheet trouvé (méthode 3): {datasheet_link}")
                            break
                
            except Exception as e:
                self.logger.debug(f"Erreur extraction datasheet: {e}")
            
            # ÉTAPE 4: Extraire l'image du produit
            try:
                # Méthode 1: Chercher les images avec alt contenant "Server"
                server_images = self.driver.find_elements(By.XPATH, "//img[contains(@alt, 'Server')]")
                if server_images:
                    image_url = server_images[0].get_attribute('src')
                    self.logger.info(f"✅ Image trouvée (méthode 1): {image_url}")
                
                # Méthode 2: Chercher les images avec src contenant "fusionserver"
                if not image_url:
                    fusionserver_images = self.driver.find_elements(By.XPATH, "//img[contains(@src, 'fusionserver')]")
                    if fusionserver_images:
                        image_url = fusionserver_images[0].get_attribute('src')
                        self.logger.info(f"✅ Image trouvée (méthode 2): {image_url}")
                
                # Méthode 3: Chercher dans les images de bannière
                if not image_url:
                    banner_images = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'banner')]//img")
                    if banner_images:
                        image_url = banner_images[0].get_attribute('src')
                        self.logger.info(f"✅ Image trouvée (méthode 3): {image_url}")
                
            except Exception as e:
                self.logger.debug(f"Erreur extraction image: {e}")
            
            # Fermer l'onglet et revenir au principal
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            
        except Exception as e:
            self.logger.debug(f"Erreur extraction détails produit {product_url}: {e}")
            # S'assurer de revenir à l'onglet principal en cas d'erreur
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
        
        return datasheet_link, image_url, detailed_specs
    
    def extract_rack_scale_servers(self, url):
        """Extrait les serveurs Rack-Scale (format cartes)"""
        servers = []
        
        try:
            self.driver.get(url)
            time.sleep(5)
            
            # Scroll pour charger tout le contenu
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Chercher toutes les sections avec jiedian_list
            sections = self.driver.find_elements(By.CSS_SELECTOR, ".jiedian_list")
            self.logger.info(f"🔍 Trouvé {len(sections)} sections jiedian_list")
            
            for i, section in enumerate(sections):
                try:
                    # Extraire les spécifications depuis les items
                    specs = {}
                    items = section.find_elements(By.CSS_SELECTOR, ".jiedian_list_item")
                    
                    name = ""
                    for item in items:
                        try:
                            title_elem = item.find_element(By.CSS_SELECTOR, ".left_title")
                            desc_elem = item.find_element(By.CSS_SELECTOR, ".right_desc")
                            
                            title = title_elem.text.strip()
                            desc = desc_elem.text.strip()
                            
                            if title == "Model":
                                name = desc
                            else:
                                specs[title] = desc
                                
                        except Exception as e:
                            self.logger.debug(f"Erreur item {i}: {e}")
                            continue
                    
                    if name:
                        # Construire le lien
                        if "DH122E V6" in name:
                            link = "https://www.xfusion.com/en/product/rack-scale-servers/dh122e-v6"
                        elif "DH120E V7" in name:
                            link = "https://www.xfusion.com/en/product/rack-scale-servers/fusionpod-dh120e-v7"
                        else:
                            link = f"https://www.xfusion.com/en/product/rack-scale-servers/{name.lower().replace(' ', '-')}"
                        
                        server_data = {
                            "brand": "XFusion",
                            "category": "Rack-Scale Servers",
                            "name": name,
                            "link": link,
                            "tech_specs": specs,
                            "scraped_at": datetime.now().isoformat(),
                            "datasheet_link": "",
                            "image_url": ""
                        }
                        
                        # Extraire les liens datasheet, image et spécifications détaillées depuis la page produit
                        datasheet_link, image_url, detailed_specs = self.extract_product_details(link)
                        server_data["datasheet_link"] = datasheet_link
                        server_data["image_url"] = image_url
                        
                        # Remplacer les spécifications basiques par les détaillées si disponibles
                        if detailed_specs:
                            server_data["tech_specs"] = detailed_specs
                            self.logger.info(f"✅ Spécifications détaillées remplacées pour: {name}")
                        
                        servers.append(server_data)
                        self.logger.info(f"✅ Serveur Rack-Scale {i+1}: {name}")
                        
                except Exception as e:
                    self.logger.error(f"Erreur extraction section {i}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Erreur scraping Rack-Scale: {e}")
            
        return servers
    
    def extract_fusionpod_ai(self, url):
        """Extrait les données FusionPoD for AI"""
        try:
            self.driver.get(url)
            time.sleep(5)
            
            # Extraire les spécifications
            specs = {}
            spec_elements = self.driver.find_elements(By.CSS_SELECTOR, ".jieshao_feature")
            
            for element in spec_elements:
                try:
                    key_elem = element.find_element(By.CSS_SELECTOR, ".jieshao_feature_num")
                    value_elem = element.find_element(By.CSS_SELECTOR, ".jieshao_feature_text")
                    
                    key = key_elem.text.strip()
                    value = value_elem.text.strip()
                    
                    specs[value] = key
                    
                except:
                    continue
            
            server_data = {
                "brand": "XFusion",
                "category": "FusionPoD for AI",
                "name": "FusionPoD for AI",
                "link": url,
                "tech_specs": specs,
                "scraped_at": datetime.now().isoformat(),
                "datasheet_link": "",
                "image_url": ""
            }
            
            # Extraire les liens datasheet, image et spécifications détaillées depuis la page produit
            datasheet_link, image_url, detailed_specs = self.extract_product_details(url)
            server_data["datasheet_link"] = datasheet_link
            server_data["image_url"] = image_url
            
            # Remplacer les spécifications basiques par les détaillées si disponibles
            if detailed_specs:
                server_data["tech_specs"] = detailed_specs
                self.logger.info(f"✅ Spécifications détaillées remplacées pour: FusionPoD for AI")
            
            return [server_data]
            
        except Exception as e:
            self.logger.error(f"Erreur scraping FusionPoD AI: {e}")
            return []
    
    def scrape_all_categories(self):
        """Scrape toutes les catégories"""
        all_servers = []
        
        self.setup_driver()
        
        try:
            for category, url in self.categories.items():
                self.logger.info(f"🔍 Scraping {category}...")
                
                if category == "Rack-Scale Servers":
                    servers = self.extract_rack_scale_servers(url)
                elif category == "FusionPoD for AI":
                    servers = self.extract_fusionpod_ai(url)
                else:
                    servers = self.extract_table_servers_improved(url, category)
                
                all_servers.extend(servers)
                self.logger.info(f"✅ {category}: {len(servers)} serveurs trouvés")
                
                time.sleep(2)  # Pause entre les catégories
                
        finally:
            if self.driver:
                self.driver.quit()
        
        return all_servers
    
    def save_to_json(self, servers, filename="xfusion_servers_improved.json"):
        """Sauvegarde les données en JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(servers, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"💾 Données sauvegardées dans {filename}")


def main():
    scraper = XFusionServerScraperImproved()
    
    logger.info("🚀 Démarrage du scraping XFusion amélioré...")
    
    servers = scraper.scrape_all_categories()
    
    if servers:
        scraper.save_to_json(servers)
        
        # Afficher le résumé
        print("\n📊 RÉSUMÉ DU SCRAPING AMÉLIORÉ:")
        print(f"Total serveurs: {len(servers)}")
        
        # Compter par catégorie
        categories_count = {}
        for server in servers:
            category = server['category']
            categories_count[category] = categories_count.get(category, 0) + 1
        
        for category, count in categories_count.items():
            print(f"  {category}: {count} serveurs")
    else:
        logger.warning("❌ Aucun serveur trouvé!")


if __name__ == "__main__":
    main()
