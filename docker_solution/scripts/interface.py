import tkinter as tk
from tkinter import messagebox
import json
import LLM_v2  
import yfinance as yf
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

rss_feeds = [
    {"source": "Les Echos", "url": "https://services.lesechos.fr/rss/les-echos-finance-marches.xml"},
    {"source": "La Tribune", "url": "https://www.latribune.fr/rss/rubriques/entreprises.html"}
]

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Application")
        self.geometry("800x600")

        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for PageClass in (PageOne, PageTwo):
            page = PageClass(parent=container, controller=self)
            self.frames[PageClass] = page
            page.grid(row=0, column=0, sticky="nsew")

        self.show_frame(PageOne)

    def show_frame(self, page_class):
        """Affiche la page demandée."""
        frame = self.frames[page_class]
        frame.tkraise()

class PageOne(tk.Frame):
    """
    Page 1 : Recherche d'actualités et données boursières.
    Permet de poser une question, d'extraire des entreprises via un LLM,
    d'obtenir les données financières via une requête SQL et d'afficher un graphique.
    """
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        label_question = tk.Label(self, text="Posez votre question sur l'actualité :")
        label_question.pack(pady=5)
        self.entry_question = tk.Entry(self, width=50)
        self.entry_question.pack(pady=5)

        button_submit = tk.Button(self, text="Soumettre", command=self.poser_question)
        button_submit.pack(pady=5)

        self.output_companies = tk.StringVar()
        label_companies = tk.Label(self, textvariable=self.output_companies, justify="left")
        label_companies.pack(pady=5)

        button_to_rss = tk.Button(self, text="Consulter les actualités", 
                                  command=lambda: controller.show_frame(PageTwo))
        button_to_rss.pack(pady=5)

        self.chart_frame = tk.Frame(self)
        self.chart_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.output_results = tk.StringVar()
        label_results = tk.Label(self, textvariable=self.output_results, justify="left", font=("Courier", 8))
        label_results.pack(pady=5)

    def poser_question(self):
        question = self.entry_question.get()
        if not question.strip():
            messagebox.showwarning("Entrée invalide", "Veuillez entrer une question.")
            return

        companies = LLM_v2.extract_company_from_question(question)
        if not companies:
            messagebox.showinfo("Aucun résultat", "Aucune entreprise mentionnée trouvée dans la question.")
            return
        else:
            companies_text = "\n".join(companies)
            self.output_companies.set(f"Entreprises identifiées :\n{companies_text}")

        results = {}
        valid_ticker = None
        for company in companies:
            ticker = LLM_v2.get_ticker_from_company_name(company)
            if ticker:
                sql_query = LLM_v2.generate_sql_select(ticker)
                records = LLM_v2.execute_sql_query(sql_query)
                if records and len(records) > 0:
                    last_record = records[-1]
                    date_val = last_record[0]
                    high_price_val = last_record[1]
                    low_price_val = last_record[2]
                else:
                    date_val = None
                    high_price_val = None
                    low_price_val = None

                results[company] = {
                    "ticker": ticker,
                    "date": date_val,
                    "stock_data": {
                        "high_price": high_price_val,
                        "low_price": low_price_val
                    }
                }
                if valid_ticker is None:
                    valid_ticker = ticker
            else:
                results[company] = {
                    "ticker": "N/A",
                    "date": None,
                    "stock_data": {
                        "high_price": None,
                        "low_price": None
                    }
                }
        self.output_results.set(f"=== Résultats ===\n{json.dumps(results, indent=2, ensure_ascii=False)}")

        if valid_ticker:
            self.plot_stock_history(valid_ticker)

    def plot_stock_history(self, ticker):
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")
        if hist.empty:
            messagebox.showinfo("Données manquantes", "Aucune donnée historique disponible pour le ticker.")
            return

        hist.reset_index(inplace=True)
        x = np.arange(len(hist))
        close_prices = hist["Close"].values
        slope, intercept = np.polyfit(x, close_prices, 1)
        trend_line = slope * x + intercept

        fig = Figure(figsize=(6, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(hist["Date"], hist["High"], label="High Price", marker="o")
        ax.plot(hist["Date"], hist["Low"], label="Low Price", marker="o")
        ax.plot(hist["Date"], trend_line, label="Trend (Close Price)", linestyle="--")
        ax.set_title(f"Historique pour {ticker}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Prix")
        ax.legend()
        fig.autofmt_xdate()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)



class PageTwo(tk.Frame):
    """
    Page 2 : Recherche d'actualités via flux RSS.
    Utilise la fonction get_keywords_from_question pour extraire des mots-clés,
    puis récupère les articles pertinents depuis plusieurs flux RSS.
    Un slider permet ensuite de naviguer dans les articles récupérés.
    """
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.articles = []
        
        label_question_actualite = tk.Label(self, text="Posez votre question sur l'actualité :")
        label_question_actualite.pack(pady=5)
        self.entry_question_actualite = tk.Entry(self, width=50)
        self.entry_question_actualite.pack(pady=5)

        button_actualite = tk.Button(self, text="Rechercher Actualité", command=self.poser_question_actualite)
        button_actualite.pack(pady=5)

        self.output_keywords = tk.StringVar()
        label_keywords = tk.Label(self, textvariable=self.output_keywords, justify="left", fg="blue")
        label_keywords.pack(pady=5)

        self.article_display = tk.Label(self, text="", justify="left", font=("Courier", 9), wraplength=700)
        self.article_display.pack(pady=5)

        self.slider = None

        button_back = tk.Button(self, text="Retour à l'accueil",
                                command=lambda: controller.show_frame(PageOne))
        button_back.pack(pady=5)

    def poser_question_actualite(self):
        question = self.entry_question_actualite.get()
        if not question.strip():
            messagebox.showwarning("Entrée invalide", "Veuillez entrer une question sur l'actualité.")
            return

        keywords = LLM_v2.get_keywords_from_question(question)
        if not keywords:
            messagebox.showinfo("Aucun mot-clé", "Aucun mot-clé identifié dans la question.")
            return
        self.output_keywords.set(f"Mots-clés identifiés : {', '.join(keywords)}")

        articles_all = []
        for feed in rss_feeds:
            articles = LLM_v2.recuperer_articles_by_keywords(feed["url"], keywords)
            if articles:
                for article in articles:
                    article["source"] = feed["source"]
                articles_all.extend(articles)

        if articles_all:
            self.articles = articles_all
            if self.slider is not None:
                self.slider.destroy()
            self.slider = tk.Scale(self, from_=0, to=len(self.articles)-1, orient="horizontal",
                                   command=self.update_article_display, label="Article n°")
            self.slider.pack(pady=10, fill="x")
            self.update_article_display(0)
        else:
            self.article_display.config(text="Aucun article pertinent trouvé.")

    def update_article_display(self, index_value):
        """
        Met à jour l'affichage de l'article courant en fonction de l'index sélectionné par le slider.
        """
        index = int(index_value)
        if 0 <= index < len(self.articles):
            article = self.articles[index]
            text = f"Source: {article['source']}\n" \
                   f"Titre: {article['titre']}\n" \
                   f"Date: {article['date']}\n" \
                   f"Lien: {article['lien']}\n" \
                   f"Description: {article['description']}"
            self.article_display.config(text=text)
        else:
            self.article_display.config(text="Index hors limites.")

if __name__ == "__main__":
    app = App()
    app.mainloop()
