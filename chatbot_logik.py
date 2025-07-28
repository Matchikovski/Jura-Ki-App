import google.generativeai as genai
import os
import streamlit as st
from datenbank import finde_relevantesten_fall
from tenacity import retry, stop_after_attempt, wait_random_exponential

# Konfiguriert die Gemini API mit st.secrets
try:
    # Greift auf den Key aus der secrets.toml zu
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except (AttributeError, KeyError):
    pass 

# Vollständiger Prompt für den RAG-Assistenten
system_prompt_rag_assistent = """
Du bist ein "JuraKI-Tutor", ein freundlicher und präziser Tutor für Jurastudenten.

Deine Aufgabe ist es, die Frage des Studenten zu beantworten. Du erhältst dafür möglicherweise einen "KONTEXT" aus einer Falldatenbank.

DEIN VORGEHEN:
1.  Prüfe zuerst, ob der "KONTEXT" thematisch zur "FRAGE DES STUDENTEN" passt.
2.  **Wenn der Kontext passt:** Beantworte die Frage des Studenten präzise und AUSSCHLIESSLICH auf Basis der Informationen im Kontext. Beginne deine Antwort, indem du den Fall-Titel nennst.
3.  **Wenn der Kontext NICHT passt oder fehlt:** Ignoriere den Kontext vollständig. Beantworte die Frage des Studenten basierend auf deinem allgemeinen Wissen zum deutschen Zivilrecht. Beginne deine Antwort mit dem Satz: "Ich konnte keinen spezifischen Fall dazu in meiner Datenbank finden, aber allgemein gilt:".
4.  Gib unter keinen Umständen Rechtsberatung, sondern nur didaktische Erklärungen.
"""

@st.cache_data(ttl=3600)
@retry(
    wait=wait_random_exponential(min=1, max=10),
    stop=stop_after_attempt(2)
)
def get_chatbot_response(user_query, _faelle, _modell, _fall_embeddings):
    """
    Orchestriert den RAG-Prozess.
    Beachte die Unterstriche bei den Argumenten, um Caching-Fehler zu vermeiden.
    """
    
    # Stufe 1: Retrieval (Semantische Suche)
    kontext_fall = finde_relevantesten_fall(user_query, _faelle, _modell, _fall_embeddings)
    
    # Stufe 2: Augmented Generation (Antworten)
    input_prompt = ""
    if not kontext_fall:
        input_prompt = f'KONTEXT: Kein passender Kontext gefunden. FRAGE DES STUDENTEN: "{user_query}"'
    else:
        input_prompt = f"""
        KONTEXT:
        - Fall-Titel: {kontext_fall['fall_titel']}
        - Zentrales Problem: {kontext_fall['zentrales_problem']}
        - Kernfrage: {kontext_fall['kernfrage']}
        - Kurzlösung: {kontext_fall['kurzloesung']}

        FRAGE DES STUDENTEN:
        "{user_query}"
        """
    
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest", system_instruction=system_prompt_rag_assistent)
        response = model.generate_content(input_prompt)
        kontext_titel = kontext_fall['fall_titel'] if kontext_fall else None
        return response.text, kontext_titel
    except Exception as e:
        print(f"Fehler in get_chatbot_response nach 2 Versuchen: {e}")
        return "Entschuldigung, bei der Generierung der Antwort ist ein Fehler aufgetreten. Bitte versuchen Sie es später erneut.", None
