# gamification_logik.py

# Definition aller möglichen Erfolge
# Jeder Erfolg hat eine ID, einen Namen, eine Beschreibung und eine Bedingung.
ACHIEVEMENTS = {
    "first_case": {
        "name": "Paragraphen-Pionier",
        "description": "Du hast deine erste Klausur erfolgreich bewertet!",
        "icon": "🚀"
    },
    "bgb_beginner": {
        "name": "BGB-Entdecker",
        "description": "Schließe 5 Zivilrechtsfälle erfolgreich ab.",
        "icon": "📘"
    },
    "high_score": {
        "name": "Gutachten-Guru",
        "description": "Erreiche eine Bewertung von 90% oder mehr in einer Klausur.",
        "icon": "🏆"
    },
    "streak_3": {
        "name": "Am Ball geblieben",
        "description": "Löse an 3 verschiedenen Tagen eine Klausur.",
        "icon": "🔥"
    },
    "exam_ready": {
        "name": "Examens-Kandidat",
        "description": "Schließe eine Klausur der Schwierigkeit 5 ab.",
        "icon": "⚖️"
    }
}

def check_achievements(lernhistorie, unlocked_achievements):
    """
    Überprüft die Lernhistorie auf neue, freigeschaltete Erfolge.
    Gibt eine Liste der neu freigeschalteten Erfolge zurück.
    """
    newly_unlocked = []
    
    # Bereits freigeschaltete Erfolge als Set für eine schnelle Überprüfung
    unlocked_ids = {a['id'] for a in unlocked_achievements}

    # --- Bedingungen für die Erfolge prüfen ---

    # Erfolg: Erster Fall
    if "first_case" not in unlocked_ids and len(lernhistorie) >= 1:
        newly_unlocked.append({"id": "first_case", **ACHIEVEMENTS["first_case"]})

    # Erfolg: 5 BGB-Fälle
    if "bgb_beginner" not in unlocked_ids and len(lernhistorie) >= 5:
        newly_unlocked.append({"id": "bgb_beginner", **ACHIEVEMENTS["bgb_beginner"]})

    # Erfolg: Hohe Punktzahl
    if "high_score" not in unlocked_ids:
        if any(e.get('bewertung', 0) >= 90 for e in lernhistorie):
            newly_unlocked.append({"id": "high_score", **ACHIEVEMENTS["high_score"]})
    
    # Erfolg: Schwierigkeit 5
    if "exam_ready" not in unlocked_ids:
        if any(e.get('schwierigkeit', 0) == 5 for e in lernhistorie):
            newly_unlocked.append({"id": "exam_ready", **ACHIEVEMENTS["exam_ready"]})

    # Erfolg: 3-Tage-Serie
    if "streak_3" not in unlocked_ids and len(lernhistorie) > 0:
        # Extrahiere die Tage (ohne Uhrzeit) aus der Lernhistorie
        unique_days = {e['datum'].date() for e in lernhistorie}
        if len(unique_days) >= 3:
            newly_unlocked.append({"id": "streak_3", **ACHIEVEMENTS["streak_3"]})
            
    return newly_unlocked
