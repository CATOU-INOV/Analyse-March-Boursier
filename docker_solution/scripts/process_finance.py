import os

os.environ["PYSPARK_PYTHON"] = "/Users/thomascat/Projets/Ynov/AMB/Analyse-March-Boursier/docker_solution/scripts/venv/bin/python3.11"
os.environ["PYSPARK_DRIVER_PYTHON"] = "/Users/thomascat/Projets/Ynov/AMB/Analyse-March-Boursier/docker_solution/scripts/venv/bin/python3.11"


from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf, PandasUDFType
import pandas as pd
import numpy as np

# Chemin vers le driver JDBC
jdbc_jar_path = "/Users/thomascat/Projets/Ynov/AMB/Analyse-March-Boursier/docker_solution/drivers/mariadb-java-client-3.5.0.jar"

# Création de la session Spark avec le driver JDBC dans le classpath
spark = SparkSession.builder \
    .appName("Calcul des mesures financières par date") \
    .config("spark.jars", jdbc_jar_path) \
    .getOrCreate()

# URL JDBC et propriétés de connexion vers MariaDB
jdbc_url = "jdbc:mariadb://localhost:3306/AMB?sessionVariables=sql_mode=ANSI_QUOTES"
connection_properties = {
    "user": "nifi_user",
    "password": "nifi_password",
    "driver": "org.mariadb.jdbc.Driver",
    "useServerPrepStmts": "false"
}

# Lecture de la table financial_data depuis MariaDB.
# La table doit contenir au moins les colonnes : company_name, date, close_price et volume.
df = spark.read.jdbc(url=jdbc_url, table="financial_data", properties=connection_properties)

# Définition d'une Pandas UDF pour calculer, pour chaque date d'un groupe (par entreprise),
# les mesures à partir de l'historique jusqu'à cette date.
@pandas_udf("company_name string, date date, volatility double, trend double, average_volume double", PandasUDFType.GROUPED_MAP)
def compute_metrics_by_date_udf(pdf: pd.DataFrame) -> pd.DataFrame:
    # Trier par date (important pour un calcul chronologique)
    pdf = pdf.sort_values("date")
    results = []
    # Pour chaque ligne (date) dans le groupe, on calcule les mesures avec toutes les données historiques jusqu'à cette date.
    for idx, row in pdf.iterrows():
        # Sélectionner les données jusqu'à la date courante
        current_data = pdf[pdf["date"] <= row["date"]]
        # Conversion explicite en float pour permettre les calculs mathématiques
        closes = current_data["close_price"].dropna().astype(float).values
        volumes = current_data["volume"].dropna().astype(float).values
        
        # Calcul de la volatilité et de la tendance
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
        
        # Calcul du volume moyen
        average_volume = float(np.mean(volumes)) if len(volumes) > 0 else 0.0
        
        # Conserver le résultat pour cette date
        results.append({
            "company_name": row["company_name"],
            "date": row["date"],
            "volatility": volatility,
            "trend": trend,
            "average_volume": average_volume
        })
    
    return pd.DataFrame(results)

# Appliquer la fonction par groupe (par entreprise)
df_metrics_by_date = df.groupBy("company_name").apply(compute_metrics_by_date_udf)

# Afficher un aperçu des résultats
df_metrics_by_date.show()

# Enregistrer le résultat dans une nouvelle table "financial_measures_by_date" dans MariaDB
df_metrics_by_date.write.jdbc(url=jdbc_url, table="financial_measures_by_date", mode="overwrite", properties=connection_properties)

# Arrêter la session Spark
spark.stop()
