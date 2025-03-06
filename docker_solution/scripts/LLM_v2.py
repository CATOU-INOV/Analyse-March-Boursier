import yfinance as yf
import json
import re
import requests
import numpy as np
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
import mariadb
import feedparser
import re

# -----------------------------
# Extraction du nom d'entreprise depuis la question
# -----------------------------
def extract_company_from_question(question):
    """
    Utilise un pipeline NER basé sur Transformers pour extraire le nom d'une entreprise
    depuis la question.
    """
    # Chargement du tokenizer et du modèle NER pour le français
    tokenizer = AutoTokenizer.from_pretrained("Jean-Baptiste/camembert-ner")
    model = AutoModelForTokenClassification.from_pretrained("Jean-Baptiste/camembert-ner")
    ner_pipeline = pipeline(
        "ner",
        model=model,
        tokenizer=tokenizer,
        aggregation_strategy="simple"
    )
    
    ner_results = ner_pipeline(question)
    companies = [entity["word"].strip() for entity in ner_results if entity.get("entity_group") == "ORG"]
    
    # Si aucune entité n'est trouvée, on vérifie manuellement la présence de "tesla"
    if not companies and "tesla" in question.lower():
        companies.append("Tesla")
        
    return companies

# -----------------------------
# Récupération du ticker via Yahoo Finance
# -----------------------------
def get_ticker_from_company_name(company_name):
    """
    Interroge l'API Yahoo Finance pour obtenir le ticker associé au nom de l'entreprise.
    """
    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {"q": company_name, "quotesCount": 1, "newsCount": 0}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0 Safari/537.36"
        )
    }
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code != 200:
        print(f"Erreur lors de la récupération des données (code {response.status_code}).")
        return None

    try:
        data = response.json()
    except Exception as e:
        print("Erreur lors de la conversion de la réponse en JSON :", e)
        return None

    try:
        ticker = data["quotes"][0]["symbol"]
        return ticker
    except (IndexError, KeyError) as e:
        print("Erreur lors de l'extraction du ticker :", e)
        return None

# -----------------------------
# Calcul de métriques à partir d'un historique boursier
# -----------------------------
def compute_metrics(hist):
    """
    Calcule la volatilité (écart-type des rendements logarithmiques) et
    la tendance (pente de la régression linéaire sur les prix de clôture)
    à partir d'un DataFrame historique.
    """
    closes = hist["Close"].dropna().values
    volumes = hist["Volume"].dropna().values

    if len(closes) < 2:
        volatility = 0.0
        trend = 0.0
    else:
        try:
            log_returns = np.diff(np.log(closes))
            volatility = float(np.std(log_returns))
        except Exception as e:
            print("Erreur lors du calcul de la volatilité:", e)
            volatility = 0.0

        try:
            x = np.arange(len(closes))
            slope, _ = np.polyfit(x, closes, 1)
            trend = float(slope)
        except Exception as e:
            print("Erreur lors du calcul de la tendance:", e)
            trend = 0.0

    average_volume = float(np.mean(volumes)) if len(volumes) > 0 else 0.0
    return {"volatility": volatility, "trend": trend, "average_volume": average_volume}

# -----------------------------
# Récupération des données boursières pour un ticker sur une période donnée
# -----------------------------
def get_stock_data(ticker, period="6mo"):
    """
    Récupère les données boursières du ticker sur une période donnée (ici par défaut 6 mois)
    et calcule quelques métriques à partir des 30 derniers jours de cotation.
    """
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    hist.reset_index(inplace=True)
    info = stock.info
    company_name = info.get("longName", ticker)

    if not hist.empty:
        # On utilise les 30 derniers jours pour les métriques (si disponibles)
        hist_30 = hist.tail(30) if len(hist) >= 30 else hist
        metrics = compute_metrics(hist_30)
        latest = hist.iloc[-1]
        stock_data = {
            "ticker": ticker,
            "company_name": company_name,
            "date": str(latest["Date"].date()),
            "open_price": float(latest["Open"]),
            "close_price": float(latest["Close"]),
            "high_price": float(latest["High"]),
            "low_price": float(latest["Low"]),
            "volume": int(latest["Volume"]),
            "volatilite": metrics["volatility"],
            "tendance": metrics["trend"],
            "volume_moyen": metrics["average_volume"]
        }
        return stock_data
    else:
        return None

# -----------------------------
# Génération d'une requête SQL SELECT pour récupérer les données sur 6 mois
# -----------------------------
def generate_sql_select(ticker):
    """
    Génère une requête SQL permettant d'extraire les données boursières de l'entreprise
    identifiée par le ticker sur les six derniers mois.
    La table utilisée est 'stock_data' et l'on suppose que la colonne stock_date est au format DATE.
    """
    sql = (
        f"SELECT * FROM financial_data "
        f"WHERE ticker = '{ticker}' "
        f"AND date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH);"
    )
    return sql

def execute_sql_query(sql_query):
    """
    Se connecte à la base de données MariaDB et exécute la requête SQL fournie.
    """
    connection = None  # Initialisation de la variable
    try:
        # Paramètres de connexion à la base de données dans un conteneur Docker
        connection = mariadb.connect(
            host='127.0.0.1',          # Nom du service Docker ou l'adresse IP du conteneur
            port=3306,                # Port par défaut pour MariaDB
            user='nifi_user',         # Nom d'utilisateur de la base de données
            password='nifi_password', # Mot de passe de la base de données
            database='AMB'            # Nom de la base de données
        )

        print("Connexion réussie à la base de données")

        # Création d'un curseur pour exécuter la requête
        cursor = connection.cursor()

        # Exécution de la requête SQL
        cursor.execute(sql_query)

        # Récupération des résultats
        records = cursor.fetchall()

        # Affichage des résultats
        print("\n=== Résultats de la requête ===")
        for row in records:
            print(row)

    except mariadb.Error as e:
        print("Erreur lors de la connexion ou de l'exécution de la requête :", e)

    finally:
        if connection is not None:
            connection.close()
            print("\nConnexion à la base de données fermée")

def get_keywords_from_question(question):
    """
    Transforme la question en une liste de mots-clés pour rechercher des articles d'actualité.
    Cette implémentation simplifiée extrait les mots significatifs en filtrant quelques stopwords.
    Exemple de résultat attendu : ["superbowl", "impact", "sports"]
    """
    stopwords = {
        "le", "la", "les", "de", "des", "du", "et", "en", "un", "une",
        "pour", "dans", "sur", "avec", "a", "à", "ce", "cette", "ces",
        "est", "sont", "qui", "que", "quoi", "où", "quand", "comment",
        "entre", "quelle", "est", "au", "quel"
    }
    words = re.findall(r'\w+', question.lower())
    keywords = [word for word in words if word not in stopwords and len(word) > 2]
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)
    return unique_keywords

def recuperer_articles_by_keywords(feed_url, keywords):
    """
    Extrait les articles d'un flux RSS dont le titre contient au moins un des mots-clés.
    Retourne une liste de dictionnaires contenant le titre, la description, le lien et la date.
    """
    flux = feedparser.parse(feed_url)
    articles = []
    for entry in flux.entries:
        titre = entry.get("title", "")
        description = entry.get("description", "Description non disponible")
        if any(keyword.lower() in titre.lower() for keyword in keywords):
            articles.append({
                "titre": titre,
                "description": description,
                "lien": entry.get("link", "Lien non disponible"),
                "date": entry.get("published", "Date non disponible")
            })
    return articles
# -----------------------------
# Programme principal
# -----------------------------
if __name__ == "__main__":
    # Question posée
    question = input("Posez votre question sur l'actualité : ").strip()
    print("Question :", question)
    
    # Extraction du nom d'entreprise depuis la question grâce au LLM (NER)
    companies = extract_company_from_question(question)
    if not companies:
        print("Aucune entreprise identifiée dans la question.")
        exit(0)
    
    # Pour ce cas, on prend la première entreprise extraite
    company = companies[0]
    print("Entreprise identifiée :", company)
    
    # Récupération du ticker via Yahoo Finance
    ticker = get_ticker_from_company_name(company)
    if not ticker:
        print(f"Ticker non trouvé pour l'entreprise '{company}'.")
        exit(0)
    print("Ticker identifié :", ticker)
    
    # (Optionnel) Récupération des données boursières sur 6 mois et calcul de la tendance
#    stock_data = get_stock_data(ticker, period="6mo")
#    if stock_data:
#        print("Données boursières récentes :", json.dumps(stock_data, indent=2, ensure_ascii=False))
#    else:
#        print("Aucune donnée boursière trouvée pour le ticker.")
    
    # Génération de la requête SQL permettant de trouver les données pour les 6 derniers mois
    sql_query = generate_sql_select(ticker)
    print("\n=== Requête SQL générée ===")
    print(sql_query)

    # Exécution de la requête SQL
    execute_sql_query(sql_query)