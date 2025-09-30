import google.generativeai as genai
import json
import logging
import os
from typing import Dict, List, Any
import time
import argparse
import re
from dotenv import load_dotenv
try:
    # When executed as a package module
    from .policies import FIELD_POLICY
except Exception:
    # When executed as a standalone script from project root
    from ai_processing.policies import FIELD_POLICY

# Charger les variables d'environnement depuis un fichier .env (facilite l'usage local)
load_dotenv()

# Configuration de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


AI_POLICY_STRICT = _env_bool("AI_POLICY_STRICT", True)
AI_KEYS_MAX = int(os.getenv("AI_KEYS_MAX", "30"))
AI_DROP_DESCRIPTION = _env_bool("AI_DROP_DESCRIPTION", True)


def infer_category(file_or_name: str, default_cat: str | None = None) -> str:
    name = os.path.basename(file_or_name).lower()
    if "serveur" in name or "servers" in name:
        return "serveurs"
    if "stock" in name or "storage" in name:
        return "stockage"
    return default_cat or "imprimantes_scanners"


def _canonical_key(k: str, category: str) -> str:
    k1 = re.sub(r"\s+", "_", k.strip().lower())
    syn = FIELD_POLICY.get(category, {}).get("synonyms", {})
    return syn.get(k1, k1)


def _filter_and_normalize(obj: Dict[str, Any], category: str) -> Dict[str, Any]:
    policy = FIELD_POLICY.get(category, {})
    allowed = set(policy.get("allowed", []))
    out: Dict[str, Any] = {}
    for k, v in obj.items():
        ck = _canonical_key(k, category)
        if allowed and ck not in allowed:
            continue
        val = v
        if isinstance(val, str):
            s = val.strip().replace(",", ".")
            # Normalize some simple units
            if ck.endswith("_gb"):
                m = re.search(r"([\d\.]+)\s*([tg]b?)", s, re.I)
                if m:
                    num = float(m.group(1))
                    unit = m.group(2).lower()
                    if unit.startswith("tb"):
                        num *= 1024
                    val = round(num, 2)
                else:
                    val = s
            elif ck.endswith("_mhz"):
                m = re.search(r"([\d\.]+)\s*mhz", s, re.I)
                val = int(float(m.group(1))) if m else s
            elif ck.endswith("_w"):
                m = re.search(r"([\d\.]+)\s*w", s, re.I)
                val = int(float(m.group(1))) if m else s
            else:
                val = s
        out[ck] = val
        if len(out) >= AI_KEYS_MAX:
            break
    return out

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
        
    def clean_tech_specs(self, raw_specs: Dict[str, Any], product_name: str = "", category_hint: str | None = None) -> Dict[str, Any]:
        """
        Nettoie et structure les spécifications techniques avec Gemini de manière robuste.
        """
        if not raw_specs:
            logger.warning(f"Spécifications brutes vides pour {product_name}. Retourne un dict vide.")
            return {}

        # Accepter aussi string ou JSON string
        if isinstance(raw_specs, str):
            specs_str = raw_specs.strip()
            if specs_str.startswith("{") and specs_str.endswith("}"):
                try:
                    raw_specs = json.loads(specs_str)
                except Exception:
                    raw_specs = {"Specs": specs_str}
            else:
                raw_specs = {"Specs": specs_str}
        elif not isinstance(raw_specs, dict):
            logger.warning(f"Format specs inattendu pour {product_name} ({type(raw_specs)}). Conversion textuelle.")
            raw_specs = {"Specs": str(raw_specs)}

        specs_json_string = json.dumps(raw_specs, ensure_ascii=False)
        category = category_hint or infer_category(product_name or "")

        allowed = ", ".join(FIELD_POLICY.get(category, {}).get("allowed", []))
        prompt = f"""
        Tâche : Analyse et structure les spécifications techniques suivantes pour le produit '{product_name}'.

        Règles :
        1. Extrais UNIQUEMENT les informations techniques essentielles. Supprime le marketing.
        2. Utilise des clés simples et normalisées; n’invente rien.
        3. Réponds STRICTEMENT par un objet JSON valide, sans texte additionnel.
        4. Si une information est absente, ne la crée pas.
        5. Tu ne dois pas dépasser {AI_KEYS_MAX} clés.

        Liste de clés autorisées pour cette catégorie ({category}): {allowed}

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
                generation_config = genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )
                response = self.model.generate_content(prompt, generation_config=generation_config)
                logger.info(f"✅ Spécifications nettoyées pour {product_name}")
                data = json.loads(response.text)
                if AI_POLICY_STRICT and isinstance(data, dict):
                    data = _filter_and_normalize(data, category)
                return data
            except Exception as e:
                logger.warning(f"Tentative {attempt + 1}/{max_retries} a échoué pour {product_name}: {e}")
                if attempt + 1 == max_retries:
                    logger.error(f"Échec final du traitement Gemini pour {product_name} après {max_retries} tentatives.")
                    return {"error": "Gemini processing failed", "details": str(e)}
                time.sleep(2 ** attempt)
        return {"error": "Gemini processing failed after all retries"}
    
    def process_product_batch(self, products: List[Dict[str, Any]], batch_size: int = 5, category_hint: str | None = None) -> List[Dict[str, Any]]:
        """
        Traite un lot de produits avec rate limiting
        """
        processed_products = []
        
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            
            logger.info(f"🔄 Traitement du lot {i//batch_size + 1}/{(len(products)-1)//batch_size + 1}")
            
            for product in batch:
                try:
                    # Nettoyer les spécifications (fallback si tech_specs est vide)
                    raw_specs = (
                        product.get('tech_specs')
                        or product.get('specs')
                        or product.get('specifications')
                        or product.get('features')
                        or product.get('details')
                        or product.get('description')
                        or {}
                    )
                    product_name = product.get('name', '')
                    
                    if raw_specs:
                        cleaned_specs = self.clean_tech_specs(raw_specs, product_name, category_hint=category_hint)
                        product['tech_specs'] = cleaned_specs
                        product['ai_processed'] = True
                        product['ai_processed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        product['ai_processed'] = False
                    # Option: supprimer toute description marketing si présente
                    if AI_DROP_DESCRIPTION and 'description' in product:
                        product.pop('description', None)
                    
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
        category_hint = infer_category(input_file)

        # Traiter les produits
        processed_products = processor.process_product_batch(products, category_hint=category_hint)

        # Optimiser la taille
        for product in processed_products:
            if product.get('tech_specs'):
                product['tech_specs'] = processor.optimize_specs_size(product['tech_specs'])
            # Double-sécurité: retirer description si demandé
            if AI_DROP_DESCRIPTION and 'description' in product:
                product.pop('description', None)

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
    parser = argparse.ArgumentParser(description="Nettoyage/normalisation des specs produits via Gemini")
    parser.add_argument("--in", dest="input_file", required=True, help="Fichier JSON d'entrée")
    parser.add_argument("--out", dest="output_file", required=True, help="Fichier JSON de sortie nettoyé")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("❌ GEMINI_API_KEY non définie dans l'environnement")
        raise SystemExit(2)

    process_json_file(args.input_file, args.output_file, api_key=api_key)
    logger.info(f"🧹 Nettoyage terminé: {args.output_file}")
