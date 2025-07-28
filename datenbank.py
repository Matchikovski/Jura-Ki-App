import json
import streamlit as st
from sentence_transformers import SentenceTransformer, util
import numpy as np

@st.cache_data
def lade_faelle(dateipfad):
    """Lädt die Falldatenbank aus einer JSON-Datei."""
    try:
        with open(dateipfad, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

@st.cache_resource # Das Modell wird nur einmal geladen und im Speicher gehalten
def lade_embedding_modell():
    """Lädt das Sprachmodell für die Vektor-Erstellung."""
    return SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

@st.cache_data
# HIER IST DIE KORREKTUR: 'modell' wurde zu '_modell' umbenannt.
# Dies weist Streamlit an, dieses Argument beim Caching zu ignorieren.
def erstelle_fall_embeddings(faelle, _modell):
    """Erstellt Vektor-Embeddings für alle Fälle in der Datenbank."""
    if not faelle:
        return None
    
    probleme = [fall.get('zentrales_problem', '') for fall in faelle]
    # Wir verwenden das umbenannte _modell hier ganz normal.
    return _modell.encode(probleme, convert_to_tensor=True)

# HIER IST DIE ZWEITE KORREKTUR: 'modell' wurde auch hier zu '_modell' umbenannt.
def finde_relevantesten_fall(user_query, faelle, _modell, fall_embeddings):
    """
    Findet den relevantesten Fall mittels semantischer Suche (Cosine Similarity).
    """
    if faelle is None or fall_embeddings is None:
        return None

    query_embedding = _modell.encode(user_query, convert_to_tensor=True)
    
    cos_scores = util.pytorch_cos_sim(query_embedding, fall_embeddings)[0]
    
    best_match_index = np.argmax(cos_scores)
    best_score = cos_scores[best_match_index]
    
    if best_score > 0.4:
        return faelle[best_match_index]
    else:
        return None
