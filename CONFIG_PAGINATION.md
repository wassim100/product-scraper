# 🎯 Guide de configuration ASUS Scraper

## ⚡ Configuration rapide (recommandée pour tests)
```python
MAX_PAGES_TO_SCRAPE = 2      # ~24 produits en 13 minutes
DELAY_BETWEEN_PRODUCTS = 1   # Rapide mais stable
DELAY_BETWEEN_PAGES = 2      # Évite la détection
```

## 🔄 Configuration moyenne 
```python
MAX_PAGES_TO_SCRAPE = 5      # ~60 produits en 30 minutes
DELAY_BETWEEN_PRODUCTS = 2   # Plus sûr
DELAY_BETWEEN_PAGES = 3      # Plus de sécurité
```

## 🔋 Configuration complète (tous les 124 serveurs)
```python
MAX_PAGES_TO_SCRAPE = 15     # Tous les produits en ~2h
DELAY_BETWEEN_PRODUCTS = 3   # Maximum de sécurité
DELAY_BETWEEN_PAGES = 5      # Anti-détection renforcée
```

## 📈 Progression estimée

| Pages | Produits | Temps estimé | Usage recommandé |
|-------|----------|--------------|------------------|
| 2     | ~24      | 13 min       | ✅ Tests rapides |
| 5     | ~60      | 30 min       | 🔄 Tests moyens  |
| 10    | ~120     | 1h           | 🔋 Production    |
| 15    | ~124     | 2h           | 📊 Extraction complète |

## 🛠️ Comment modifier

1. **Ouvrir** `serveurs/asus.py`
2. **Modifier** ligne 25-27 :
```python
MAX_PAGES_TO_SCRAPE = 5  # Changer ce nombre
```
3. **Relancer** le script

## 💡 Conseils

- **Tests** : Commencez par 2 pages
- **Production** : Utilisez 10-15 pages
- **Nuit** : Lancez l'extraction complète
- **Erreurs** : Réduisez les délais si ça va trop lentement
