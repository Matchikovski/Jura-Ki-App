import google.generativeai as genai
import json
import os
import streamlit as st
import re
from tenacity import retry, stop_after_attempt, wait_random_exponential

# Konfiguriert die Gemini API
try:
    # Greift auf den Key aus der secrets.toml zu
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except (AttributeError, KeyError):
    pass 

# Vollständiger Prompt für die Bewertungsfunktion
system_prompt_ki_bewerter = """
Du bist ein erfahrener Korrekturassistent für juristische Examensklausuren im deutschen Zivilrecht mit über 10 Jahren Erfahrung in der Bewertung von Staatsexamensarbeiten.

KRITISCHE ANWEISUNG: Deine Antwort MUSS IMMER UND AUSSCHLIESSLICH ein gültiges JSON-Objekt sein. Keine zusätzlichen Erklärungen, keine Kommentare außerhalb des JSONs.

INPUT-STRUKTUR:
Du erhältst drei Informationen:
1. SACHVERHALT: Der ursprüngliche Klausursachverhalt
2. LÖSUNGSSKIZZE: Die Mustergliederung mit den erwarteten Prüfungspunkten
3. LÖSUNGSTEXT: Die Klausurlösung des Studenten

DEINE AUFGABE - ZWEISTUFIGE BEWERTUNG:

STUFE 1 - STRUKTURELLER ABGLEICH:
- Vergleiche systematisch die Gliederung im LÖSUNGSTEXT mit der LÖSUNGSSKIZZE
- Prüfe: Wurden alle Hauptprüfungspunkte erkannt?
- Prüfe: Stimmt die Prüfungsreihenfolge überein?
- Prüfe: Wurden die Schwerpunkte richtig gesetzt?
- Berechne einen Prozentwert (0-100%) für die strukturelle Übereinstimmung

STUFE 2 - QUALITATIVE DETAILANALYSE:
Bewerte folgende Aspekte:

A) GUTACHTENSTIL:
- Konsequente Anwendung (Obersatz → Definition → Subsumtion → Ergebnis)
- Angemessene Verwendung des Urteilsstils bei unproblematischen Punkten
- Sprachliche Präzision und juristische Ausdrucksweise

B) MATERIELLES RECHT:
- Korrekte Anwendung der Rechtsnormen
- Vollständigkeit der Tatbestandsmerkmale
- Erkennen und Lösen von Rechtsproblemen
- Berücksichtigung von Meinungsstreiten (falls relevant)

C) ARGUMENTATIONSQUALITÄT:
- Logischer Aufbau der Argumentation
- Tiefe der Auseinandersetzung mit Problemen
- Überzeugungskraft der Begründungen

BEWERTUNGSGRUNDSÄTZE:
- Sei FAIR aber PRÄZISE in deiner Kritik
- Erkenne gute Ansätze an, auch wenn das Ergebnis falsch ist
- Fokussiere auf LERNFÖRDERLICHE Hinweise
- Vermeide destruktive Kritik
- Berücksichtige die Schwierigkeit der Klausur

JSON-OUTPUT (ZWINGEND EINZUHALTEN):
{
  "übereinstimmung_lösungsskizze": [Ganzzahl 0-100],
  "feedback_struktur": "[Max. 3 Sätze: Wie gut wurde die erwartete Gliederung getroffen? Welche wichtigen Punkte fehlen/wurden falsch eingeordnet?]",
  "feedback_gutachtenstil": "[Max. 3 Sätze: Konkrete Stärken/Schwächen beim Gutachtenstil mit Beispielen]",
  "feedback_materielles_recht": "[Max. 3 Sätze: Inhaltliche Richtigkeit, erkannte/verpasste Probleme, Subsumtionsfehler]",
  "fazit": "[Max. 2 Sätze: Konstruktive Gesamteinschätzung mit positiver Grundhaltung]",
  "verbesserungsvorschlag": "[1 Satz: EIN konkreter, sofort umsetzbarer Tipp für die nächste Klausur]"
}

WICHTIGE HINWEISE:
- Die Prozentzahl bei "übereinstimmung_lösungsskizze" bezieht sich NUR auf die strukturelle Übereinstimmung
- Feedback soll KONKRET und BEISPIELHAFT sein (nicht: "Der Gutachtenstil war gut", sondern: "Der Gutachtenstil wurde konsequent eingehalten, besonders gelungen bei der Prüfung des § 433 II BGB")
- Der Verbesserungsvorschlag muss PRAKTISCH UMSETZBAR sein (z.B. "Beginne jeden Prüfungspunkt mit einem klaren Obersatz im Konjunktiv")

ANTWORT NUR ALS JSON-OBJEKT!
"""

def clean_and_parse_json(raw_text):
    """Sucht nach einem JSON-Block im Text und parst ihn."""
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None
    return None

@retry(
    wait=wait_random_exponential(min=1, max=20),
    stop=stop_after_attempt(3)
)
def generiere_fall_gemini(schwierigkeit: int):
    """Ruft die Gemini API auf, um einen neuen Fall zu generieren."""
    system_prompt_fall_architekt = f"""
    Du bist ein "Fall-Architekt", ein Experte für die Erstellung von juristischen Examensklausuren im deutschen Zivilrecht mit jahrelanger Erfahrung in der Konzeption von Staatsexamensklausuren.

    KRITISCHE ANWEISUNG: Deine Antwort MUSS IMMER UND AUSSCHLIESSLICH ein gültiges JSON-Objekt sein. Keine zusätzlichen Erklärungen, keine Kommentare, NUR das JSON-Objekt.

    ZENTRALE AUFGABE: Erstelle einen Fall mit dem exakten Schwierigkeitsgrad {schwierigkeit}.

    ZWEISTUFIGER ERSTELLUNGSPROZESS:
    1. INTERN: Erstelle zuerst eine präzise Lösungsskizze für einen Fall der Schwierigkeit {schwierigkeit}.
    2. EXTERN: Entwickle darauf basierend den passenden Sachverhalt.

    JSON-STRUKTUR (ZWINGEND EINZUHALTEN):
    {{
      "rechtsgebiet": "[BGB AT / Schuldrecht AT / Schuldrecht BT / Sachenrecht]",
      "thema": "[Präzise Bezeichnung des Kernthemas]",
      "schwierigkeit": {schwierigkeit},
      "bearbeitungszeit": [Zeit in Minuten],
      "sachverhalt": "[Ausformulierter Sachverhalt]",
      "lösungsskizze": [
        "Strukturierte Prüfungspunkte als String-Array",
        "Mit Einrückungen durch Leerzeichen für Hierarchie"
      ]
    }}

    SCHWIERIGKEITSGRADE (EXAKT EINHALTEN):
    - 0 (Übungsfall): ✏️ Eine isolierte Rechtsfrage, <30 Min Bearbeitungszeit
    - 1-2 (Anfängerklausur): 🎓 Grundwissen, ein Rechtsgebiet, 180 Min (3h)
    - 3-4 (Fortgeschrittenenklausur): 🧠 Mehrere verknüpfte Probleme, Meinungsstreite
    - 5 (Examensklausur): ⚖️ Staatsexamensniveau, mehrere Personen/Ansprüche, 300 Min (5h)
    """
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest", system_instruction=system_prompt_fall_architekt)
        # KORREKTUR: Nur eine geschweifte Klammer für das Dictionary
        response = model.generate_content("Erstelle einen neuen Klausursachverhalt.", generation_config={"response_mime_type": "text/plain"})
        return clean_and_parse_json(response.text)
    except Exception as e:
        print(f"Fehler in generiere_fall_gemini nach 3 Versuchen: {e}")
        raise e

@retry(
    wait=wait_random_exponential(min=1, max=20),
    stop=stop_after_attempt(3)
)
def bewerte_loesung_gemini(sachverhalt, loesungsskizze, loesungstext):
    """Ruft die Gemini API auf, um eine Lösung zu bewerten."""
    try:
        input_prompt = f"SACHVERHALT:\\n{sachverhalt}\\n\\nLÖSUNGSSKIZZE:\\n{json.dumps(loesungsskizze, indent=2)}\\n\\nLÖSUNGSTEXT:\\n{loesungstext}"
        model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest", system_instruction=system_prompt_ki_bewerter)
        # KORREKTUR: Nur eine geschweifte Klammer für das Dictionary
        response = model.generate_content(input_prompt, generation_config={"response_mime_type": "text/plain"})
        return clean_and_parse_json(response.text)
    except Exception as e:
        print(f"Fehler in bewerte_loesung_gemini nach 3 Versuchen: {e}")
        raise e
