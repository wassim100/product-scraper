import google.generativeai as genai
import json
import logging
import os
from typing import Dict, List, Any
import time

# Configuration de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiProcessor:
    def __init__(self, api_key=None, model_name='gemini-1.5-flash'):
        """
        Initialise le processeur Gemini de manière optimisée.
        - model_name: 'gemini-1.5-flash' (rapide, économe) ou 'gemini-1.5-pro' (qualité supérieure)
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY non trouvée. Définissez la variable d'environnement ou passez l'API key.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)
        
    def clean_tech_specs(self, raw_specs: Dict[str, Any], product_name: str = "") -> Dict[str, Any]:
        """
        Nettoie et structure les spécifications techniques avec Gemini de manière robuste.
        """
        if not raw_specs or not isinstance(raw_specs, dict):
            logger.warning(f"Spécifications brutes vides ou invalides pour {product_name}. Retourne un dict vide.")
            return {}

        # Convertir les spécifications brutes en une chaîne JSON simple
        specs_json_string = json.dumps(raw_specs, ensure_ascii=False)

        # Prompt optimisé "few-shot" pour de meilleurs résultats et moins de tokens
        prompt = f"""
        Tâche : Analyse et structure les spécifications techniques suivantes pour le produit '{product_name}'.

        Règles :
        1. Extrais les informations clés (Processeur, Mémoire, Stockage, Réseau, etc.).
        2. Regroupe les informations de manière logique.
        3. Ignore les phrases marketing non pertinentes.
        4. Si une information est manquante, ne l'invente pas.
        5. Réponds UNIQUEMENT avec un objet JSON valide. Ne rajoute pas de texte avant ou après.

        Exemple :
        Input: {{"General": "Powered by Intel Xeon E-2300 series processors, four DDR4 DIMM slots, two M.2 slots, up to four 3.5-inch HDDs, and one 2.5-inch SSD."}}
        Output: {{
            "Processeur": {{
                "Famille": "Intel Xeon E-2300"
            }},
            "Mémoire": {{
                "Type": "DDR4",
                "Slots": "4"
            }},
            "Stockage": {{
                "HDD 3.5": "4",
                "SSD 2.5": "1",
                "M.2": "2"
            }}
        }}

        Spécifications à traiter :
        Input: {specs_json_string}
        Output:
        """

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Configuration de la génération pour une réponse JSON fiable
                generation_config = genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1 # Faible température pour des résultats plus déterministes
                )
                response = self.model.generate_content(prompt, generation_config=generation_config)
                
                # La réponse est déjà un objet JSON grâce à response_mime_type
                logger.info(f"✅ Spécifications nettoyées pour {product_name}")
                return json.loads(response.text)

            except Exception as e:
                logger.warning(f"Tentative {attempt + 1}/{max_retries} a échoué pour {product_name}: {e}")
                if attempt + 1 == max_retries:
                    logger.error(f"Échec final du traitement Gemini pour {product_name} après {max_retries} tentatives.")
                    return {"error": "Gemini processing failed", "details": str(e)}
                time.sleep(2 ** attempt)  # Attente exponentielle (1s, 2s, 4s...)
        
        return {"error": "Gemini processing failed after all retries"}
    
    def process_product_batch(self, products: List[Dict[str, Any]], batch_size: int = 5) -> List[Dict[str, Any]]:
        """
        Traite un lot de produits avec rate limiting
        """
        processed_products = []
        
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            
            logger.info(f"🔄 Traitement du lot {i//batch_size + 1}/{(len(products)-1)//batch_size + 1}")
            
            for product in batch:
                try:
                    # Nettoyer les spécifications
                    raw_specs = product.get('tech_specs', {})
                    product_name = product.get('name', '')
                    
                    if raw_specs:
                        cleaned_specs = self.clean_tech_specs(raw_specs, product_name)
                        product['tech_specs'] = cleaned_specs
                        product['ai_processed'] = True
                        product['ai_processed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        product['ai_processed'] = False
                    
                    processed_products.append(product)
                    
                except Exception as e:
                    logger.error(f"❌ Erreur traitement {product.get('name', 'Unknown')}: {e}")
                    product['ai_processed'] = False
                    processed_products.append(product)
            
            # Rate limiting pour éviter les quotas
            if i + batch_size < len(products):
                logger.info("⏳ Pause pour respecter les quotas API...")
                time.sleep(2)
        
        return processed_products
    
    def optimize_specs_size(self, specs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimise la taille des spécifications en supprimant les données redondantes
        """
        if not specs:
            return specs
        
        # Supprimer les clés vides ou avec des valeurs inutiles
        optimized = {}
        
        for category, values in specs.items():
            if isinstance(values, dict):
                filtered_values = {}
                for key, value in values.items():
                    # Garder seulement les valeurs pertinentes
                    if (value and 
                        str(value).strip() and 
                        str(value).lower() not in ['n/a', 'na', 'non disponible', 'unknown', '-', '.']):
                        filtered_values[key] = value
                
                if filtered_values:
                    optimized[category] = filtered_values
            elif (values and 
                  str(values).strip() and 
                  str(values).lower() not in ['n/a', 'na', 'non disponible', 'unknown', '-', '.']):
                optimized[category] = values
        
        return optimized

def process_json_file(input_file: str, output_file: str, api_key: str = None):
    """
    Traite un fichier JSON complet avec Gemini
    """
    try:
        # Charger les données
        with open(input_file, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        logger.info(f"📊 Traitement de {len(products)} produits avec Gemini...")
        
        # Initialiser le processeur
        processor = GeminiProcessor(api_key)
        
        # Traiter les produits
        processed_products = processor.process_product_batch(products)
        
        # Optimiser la taille
        for product in processed_products:
            if product.get('tech_specs'):
                product['tech_specs'] = processor.optimize_specs_size(product['tech_specs'])
        
        # Sauvegarder
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_products, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Traitement terminé → {output_file}")
        
        # Statistiques
        processed_count = sum(1 for p in processed_products if p.get('ai_processed'))
        logger.info(f"📈 {processed_count}/{len(processed_products)} produits traités par IA")
        
    except Exception as e:
        logger.error(f"❌ Erreur traitement fichier: {e}")

if __name__ == "__main__":
    # Test avec un exemple
    test_specs = {
        "Processor": "Intel Xeon Gold 6248R @ 3.0GHz",
        "Memory": "Up to 1TB DDR4",
        "Storage": "Multiple SSD/HDD options",
        "Network": "Dual 10GbE ports"
    }
    
    # Nécessite une clé API Gemini
    # processor = GeminiProcessor()
    # cleaned = processor.clean_tech_specs(test_specs, "Test Server")
    # print(json.dumps(cleaned, indent=2))
