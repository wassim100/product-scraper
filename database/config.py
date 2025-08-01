# Configuration de la base de données MySQL
# Modifiez ces paramètres selon votre installation MySQL

DB_CONFIG = {
    'host': 'localhost',
    'database': 'scraping_db',
    'user': 'root',
    'password': '',  # Remplacez par votre mot de passe MySQL si nécessaire
    'charset': 'utf8mb4',
    'autocommit': True
}

# Configuration alternative pour XAMPP/WAMP (décommentez si nécessaire)
# DB_CONFIG = {
#     'host': 'localhost',
#     'database': 'scraping_db',
#     'user': 'root',
#     'password': '',
#     'port': 3306,
#     'charset': 'utf8mb4',
#     'autocommit': True
# }

# Pour tester la connexion sans base de données (création initiale)
DB_CONFIG_NO_DB = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Remplacez par votre mot de passe MySQL si nécessaire
    'charset': 'utf8mb4'
}
