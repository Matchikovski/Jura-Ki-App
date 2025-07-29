import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pandas as pd

# Importe aus unseren Modulen
from datenbank import lade_faelle, lade_embedding_modell, erstelle_fall_embeddings
from klausur_logik import generiere_fall_gemini, bewerte_loesung_gemini
from chatbot_logik import get_chatbot_response
from gamification_logik import check_achievements, ACHIEVEMENTS

# --- KONFIGURATION & DATEN LADEN ---
st.set_page_config(page_title="JuraKI-Mentor", page_icon="⚖️", layout="wide")
load_dotenv()
wissensdatenbank = lade_faelle("zivilrecht-faelle-json.json")
embedding_modell = lade_embedding_modell()
fall_embeddings = erstelle_fall_embeddings(wissensdatenbank, embedding_modell)


# --- UI/UX VERBESSERUNGEN (VORSCHLAG 1) ---
def apply_custom_styling():
    """Wendet die visuelle Identität 'Examio Juris' an."""
    st.markdown("""
        <style>
            /* Import Fonts */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Source+Serif+4:opsz,wght@8..60,400;600&display=swap');

            /* Globale Variablen für Farben */
            :root {
                --primary-color: #003366; /* Tiefblau */
                --background-color: #F8F9FA; /* Off-White */
                --text-color: #212529; /* Dunkelgrau */
                --success-color: #28a745; /* Grün */
                --border-color: #dee2e6; /* Heller Rand */
            }

            /* Grundlegende Body-Styles */
            html, body, [class*="st-"] {
                font-family: 'Inter', sans-serif;
                color: var(--text-color);
                background-color: var(--background-color);
            }

            /* Spezifische Schriftart für Klausurinhalte */
            .serif-text {
                font-family: 'Source Serif 4', serif;
                line-height: 1.7;
                font-size: 1.1rem;
            }
            
            /* Buttons anpassen */
            .stButton>button {
                border: 1px solid var(--primary-color);
                color: var(--primary-color);
                border-radius: 0.5rem;
            }
            .stButton>button:hover {
                border-color: var(--primary-color);
                background-color: #f0f0f0;
                color: var(--primary-color);
            }
            /* Primärer Button */
            .stButton>button[kind="primary"] {
                background-color: var(--primary-color);
                color: white;
                border: none;
            }
            .stButton>button[kind="primary"]:hover {
                background-color: #002244; /* Dunkleres Blau */
                color: white;
            }

            /* Container für Sachverhalt und Lösung */
            .content-box {
                border: 1px solid var(--border-color);
                border-radius: 10px;
                padding: 2rem;
                background-color: white;
                height: 100%;
            }
            
            /* Verbesserte Feedback-Anzeige */
            .feedback-category {
                margin-bottom: 1.5rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid var(--border-color);
            }
        </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE INITIALISIERUNG ---
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "Klausur-Training"
if "user_profile" not in st.session_state:
    st.session_state.user_profile = None
if "current_fall" not in st.session_state:
    st.session_state.current_fall = None
if "loesung_input" not in st.session_state:
    st.session_state.loesung_input = ""
if "feedback" not in st.session_state:
    st.session_state.feedback = None
if "timer_is_active" not in st.session_state:
    st.session_state.timer_is_active = False
if "remaining_seconds" not in st.session_state:
    st.session_state.remaining_seconds = 0
if "messages" not in st.session_state:
    st.session_state.messages = []
if "lernhistorie" not in st.session_state:
    st.session_state.lernhistorie = []
if "unlocked_achievements" not in st.session_state:
    st.session_state.unlocked_achievements = []

# --- UI FUNKTIONEN ---

def show_onboarding_screen():
    """Zeigt den Willkommensbildschirm für neue Nutzer."""
    st.title("Willkommen beim JuraKI-Mentor! 👋")
    st.subheader("Lass uns die App für dich personalisieren.")
    
    with st.form(key="onboarding_form"):
        st.write("Bitte beantworte die folgenden Fragen, um dein Erlebnis zu optimieren:")
        situation = st.selectbox(
            "Was beschreibt deine aktuelle Situation am besten?",
            ("Grundstudium (1.-3. Semester)", "Hauptstudium (ab 4. Semester)", "Examensvorbereitung (1. Staatsexamen)", "Referendariat (2. Staatsexamen)")
        )
        bundesland = st.selectbox(
            "In welchem Bundesland schreibst du dein Examen?",
            ("Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen", "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen")
        )
        fokus = st.selectbox(
            "Gibt es ein Rechtsgebiet im Zivilrecht, das dir besondere Sorgen bereitet?",
            ("BGB AT", "Schuldrecht AT", "Schuldrecht BT", "Sachenrecht", "Nein, aktuell keins im Besonderen")
        )
        
        if st.form_submit_button("Profil speichern und starten"):
            schwierigkeit_mapping = {"Grundstudium (1.-3. Semester)": 1, "Hauptstudium (ab 4. Semester)": 2, "Examensvorbereitung (1. Staatsexamen)": 3, "Referendariat (2. Staatsexamen)": 4}
            start_schwierigkeit = schwierigkeit_mapping.get(situation, 2)
            st.session_state.user_profile = {"situation": situation, "bundesland": bundesland, "fokus": fokus, "start_schwierigkeit": start_schwierigkeit}
            st.success("Dein Profil wurde gespeichert!")
            st.rerun()

def render_klausur_training():
    """Rendert die Benutzeroberfläche für das Klausur-Training."""
    if not st.session_state.current_fall:
        st.info("👈 Wähle in der Seitenleiste eine Schwierigkeit und klicke auf 'Neuen Fall generieren', um zu beginnen.")
        return

    fall = st.session_state.current_fall
    if st.session_state.timer_is_active:
        st_autorefresh(interval=1000, limit=None, key="timer_countdown")
        st.session_state.remaining_seconds -= 1
        if st.session_state.remaining_seconds < 0:
            st.session_state.timer_is_active = False
            st.session_state.remaining_seconds = 0
            st.warning("Die Zeit ist abgelaufen!")

    st.header(f"Thema: {fall.get('thema', 'Unbekannt')}")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rechtsgebiet", fall.get('rechtsgebiet', 'N/A'))
    col2.metric("Schwierigkeit", f"{'⭐' * fall.get('schwierigkeit', 0)}", f"{fall.get('schwierigkeit', 0)}/5")
    col3.metric("Gesamtzeit", f"{fall.get('bearbeitungszeit', 0)} Min.")
    secs = int(st.session_state.remaining_seconds)
    timer_display = f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"
    col4.metric("Verbleibende Zeit", timer_display)
    st.divider()

    timer_cols = st.columns(3)
    if timer_cols[0].button("Start", use_container_width=True, disabled=st.session_state.timer_is_active):
        st.session_state.timer_is_active = True
        st.rerun()
    if timer_cols[1].button("Pause", use_container_width=True, disabled=not st.session_state.timer_is_active):
        st.session_state.timer_is_active = False
        st.rerun()
    if timer_cols[2].button("Reset", use_container_width=True):
        st.session_state.remaining_seconds = fall.get("bearbeitungszeit", 180) * 60
        st.session_state.timer_is_active = False
        st.rerun()
    st.divider()

    col_fall, col_loesung = st.columns(2)
    with col_fall:
        st.markdown('<div class="content-box">', unsafe_allow_html=True)
        st.subheader("📋 Aktueller Sachverhalt")
        st.markdown(f"<div class='serif-text'>{fall.get('sachverhalt', 'Fehler beim Laden.')}</div>", unsafe_allow_html=True)
        st.divider()
        with st.expander("📖 Lösungsskizze anzeigen (Spoiler!)"):
            st.text("\n".join(fall.get('lösungsskizze', ['Keine Skizze verfügbar.'])))
        st.markdown('</div>', unsafe_allow_html=True)

    with col_loesung:
        st.markdown('<div class="content-box">', unsafe_allow_html=True)
        st.subheader("✍️ Deine Lösung")
        st.text_area("Schreibe deine Lösung hier hinein:", key="loesung_input", height=400)
        
        if st.button("Lösung bewerten lassen", type="primary", use_container_width=True):
            if len(st.session_state.loesung_input) < 50:
                st.warning("Bitte gib eine ausführlichere Lösung ein, um ein aussagekräftiges Feedback zu erhalten.")
            else:
                with st.spinner("KI-Korrekturassistent analysiert deine Lösung... Dieser Vorgang kann bis zu 30 Sekunden dauern."):
                    feedback_daten = bewerte_loesung_gemini(fall['sachverhalt'], fall['lösungsskizze'], st.session_state.loesung_input)
                    st.session_state.feedback = feedback_daten
                    if feedback_daten:
                        neues_ergebnis = {"thema": fall.get('thema', 'Unbekannt'), "schwierigkeit": fall.get('schwierigkeit', 0), "bewertung": feedback_daten.get('übereinstimmung_lösungsskizze', 0), "datum": datetime.now()}
                        st.session_state.lernhistorie.append(neues_ergebnis)
                        st.toast("Dein Fortschritt wurde gespeichert!", icon="✅")
                        new_achievements = check_achievements(st.session_state.lernhistorie, st.session_state.unlocked_achievements)
                        if new_achievements:
                            st.balloons()
                            for ach in new_achievements:
                                st.session_state.unlocked_achievements.append(ach)
                                st.success(f"Erfolg freigeschaltet: {ach['icon']} {ach['name']}!")
                    else:
                        st.error("Bewertung fehlgeschlagen.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.feedback:
        st.divider()
        st.subheader("📝 Dein Feedback")
        render_feedback(st.session_state.feedback)

def render_feedback(feedback_data):
    """Rendert die Feedback-Anzeige neu und strukturiert."""
    st.success(f"**Gesamt-Fazit:** {feedback_data.get('fazit', 'N/A')}")
    st.info(f"**Verbesserungsvorschlag:** {feedback_data.get('verbesserungsvorschlag', 'N/A')}")
    st.divider()

    st.markdown('<div class="feedback-category">', unsafe_allow_html=True)
    st.markdown("<h5>Struktur & Schwerpunktsetzung</h5>", unsafe_allow_html=True)
    st.metric("Übereinstimmung mit Lösungsskizze", f"{feedback_data.get('übereinstimmung_lösungsskizze', 0)}%")
    st.markdown(feedback_data.get('feedback_struktur', 'N/A'))
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="feedback-category">', unsafe_allow_html=True)
    st.markdown("<h5>Gutachtenstil</h5>", unsafe_allow_html=True)
    st.markdown(feedback_data.get('feedback_gutachtenstil', 'N/A'))
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="feedback-category">', unsafe_allow_html=True)
    st.markdown("<h5>Materielles Recht</h5>", unsafe_allow_html=True)
    st.markdown(feedback_data.get('feedback_materielles_recht', 'N/A'))
    st.markdown('</div>', unsafe_allow_html=True)

def render_chatbot():
    """Rendert die Benutzeroberfläche für den Chatbot."""
    st.header("💬 Jura-Chatbot für das BGB AT")
    st.info("Stelle eine Frage zu einem Problem aus dem BGB AT. Ich durchsuche die Falldatenbank nach einer passenden Antwort.")
    if wissensdatenbank is None:
        st.error("Wissensdatenbank (zivilrecht-faelle-json.json) nicht gefunden.")
        return
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if prompt := st.chat_input("Was ist das Abstraktionsprinzip?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Moment, ich schlage in der Datenbank nach..."):
                antwort, kontext = get_chatbot_response(prompt, wissensdatenbank, embedding_modell, fall_embeddings)
                st.markdown(antwort)
                if kontext:
                    st.info(f"Kontext aus Fall: *{kontext}*")
        st.session_state.messages.append({"role": "assistant", "content": antwort})

def render_dashboard():
    """Rendert das Fortschritts-Dashboard."""
    st.header("📈 Dein Lernfortschritt")
    
    if not st.session_state.lernhistorie:
        st.info("Du hast noch keine Klausuren bewerten lassen. Dein Fortschritt wird hier angezeigt, sobald du deine erste Bewertung abgeschlossen hast.")
        return

    df = pd.DataFrame(st.session_state.lernhistorie)
    st.subheader("Auf einen Blick")
    col1, col2, col3 = st.columns(3)
    col1.metric("Anzahl gelöster Fälle", len(df))
    col2.metric("Durchschnittliche Bewertung", f"{df['bewertung'].mean():.1f}%")
    col3.metric("Beste Bewertung", f"{df['bewertung'].max()}%")
    st.divider()

    st.subheader("Deine Entwicklung über die Zeit")
    chart_data = df.set_index('datum')
    st.line_chart(chart_data['bewertung'])
    st.divider()

    st.subheader("🏆 Deine Erfolge")
    if not st.session_state.unlocked_achievements:
        st.info("Du hast noch keine Erfolge freigeschaltet. Löse mehr Klausuren!")
    else:
        cols = st.columns(len(ACHIEVEMENTS))
        unlocked_ids = {a['id'] for a in st.session_state.unlocked_achievements}
        for i, (ach_id, ach_data) in enumerate(ACHIEVEMENTS.items()):
            with cols[i]:
                if ach_id in unlocked_ids:
                    st.markdown(f"<div style='text-align: center; border: 2px solid #27ae60; border-radius: 10px; padding: 10px; height: 100%;'>"
                                f"<div style='font-size: 3em;'>{ach_data['icon']}</div>"
                                f"<strong>{ach_data['name']}</strong><br>"
                                f"<small>{ach_data['description']}</small>"
                                f"</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='text-align: center; opacity: 0.3; border: 2px solid gray; border-radius: 10px; padding: 10px; height: 100%;'>"
                                f"<div style='font-size: 3em;'>{ach_data['icon']}</div>"
                                f"<strong>{ach_data['name']}</strong><br>"
                                f"<small>{ach_data['description']}</small>"
                                f"</div>", unsafe_allow_html=True)
    st.divider()

    st.subheader("Letzte bearbeitete Fälle")
    df_display = df[['datum', 'thema', 'schwierigkeit', 'bewertung']].copy()
    df_display['datum'] = df_display['datum'].dt.strftime('%d.%m.%Y, %H:%M Uhr')
    df_display = df_display.rename(columns={'datum': 'Datum', 'thema': 'Thema', 'schwierigkeit': 'Schwierigkeit', 'bewertung': 'Bewertung (%)'})
    st.dataframe(df_display.sort_values(by="Datum", ascending=False), use_container_width=True)

def show_main_app():
    """Zeigt die Hauptanwendung nach dem Onboarding."""
    apply_custom_styling()
    
    with st.sidebar:
        st.title("⚖️ JuraKI-Mentor")
        st.session_state.app_mode = st.radio(
            "Wähle einen Modus:",
            ("Klausur-Training", "Jura-Chatbot (BGB AT)", "Mein Fortschritt"),
            key="mode_selection"
        )
        st.divider()

        if st.session_state.app_mode == "Klausur-Training":
            st.header("Steuerung")
            default_difficulty = st.session_state.user_profile.get("start_schwierigkeit", 3)
            gewaehlte_schwierigkeit = st.slider("Schwierigkeit auswählen", 0, 5, default_difficulty, help="0=Übungsfall, 1-2=Anfänger, 3-4=Fortgeschritten, 5=Examen")

            if st.button("Neuen Fall generieren", type="primary", use_container_width=True):
                with st.spinner("KI-Fall-Architekt entwirft einen neuen, maßgeschneiderten Fall..."):
                    fall_daten = generiere_fall_gemini(schwierigkeit=gewaehlte_schwierigkeit)
                    if fall_daten:
                        st.session_state.current_fall = fall_daten
                        st.session_state.remaining_seconds = fall_daten.get("bearbeitungszeit", 180) * 60
                        st.session_state.timer_is_active = False
                        st.session_state.feedback = None
                        st.rerun()
                    else:
                        st.error("Fehler bei der Kommunikation mit der KI.")
            
            if st.session_state.current_fall and st.button("Aktuellen Fall zurücksetzen", use_container_width=True):
                st.session_state.current_fall = None
                st.rerun()

    # --- MODUS-ROUTING ---
    if st.session_state.app_mode == "Klausur-Training":
        render_klausur_training()
    elif st.session_state.app_mode == "Jura-Chatbot (BGB AT)":
        render_chatbot()
    elif st.session_state.app_mode == "Mein Fortschritt":
        render_dashboard()

# --- HAUPTROUTINE ---
if st.session_state.user_profile is None:
    apply_custom_styling()
    show_onboarding_screen()
else:
    show_main_app()
