# Dualis Mobile Wrapper

[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen?style=for-the-badge&logo=render)](https://better-dualis.onrender.com/)

Dieses Projekt ist eine moderne, mobile-optimierte Benutzeroberfläche für das **Dualis Prüfungsportal** der DHBW.

Das offizielle Dualis-Portal ist auf Smartphones oft schwer zu bedienen, da es keine mobile Version gibt und das Design nicht responsive ist (kleine Tabellen, kein Responsive Design). Diese App löst das Problem, indem sie die Daten aus Dualis ausliest und in einem sauberen, App-ähnlichen Design darstellt.

## Wie es funktioniert

Die App fungiert als intelligenter "Mittelsmann" zwischen dir und dem Dualis-System:

1.  **Login:** Du gibst deine Matrikelnummer und dein Passwort in dieser App ein.
2.  **Verbindung:** Der Python-Server (Flask) im Hintergrund sendet diese Daten sicher an den offiziellen Dualis-Server und loggt sich für dich ein.
3.  **Datenabruf (Scraping):**
    *   Die App lädt die HTML-Seiten (Notenübersicht, Prüfungsliste) von Dualis herunter.
    *   Mithilfe von `BeautifulSoup` wird der "Datensalat" analysiert.
    *   Relevante Informationen (Modulnamen, Noten, Credits, Status) werden extrahiert.
4.  **Darstellung:** Die gewonnenen Daten werden in eine moderne Oberfläche (HTML & Tailwind CSS) gegossen, die speziell für Handys entwickelt wurde (Dark Mode, große Buttons, klare Listen).

## Technische Details

*   **Backend:** Python mit Flask
*   **Parsing:** BeautifulSoup4 (liest die HTML-Struktur von Dualis)
*   **Frontend:** HTML5 + Tailwind CSS (für das Styling)
*   **Sicherheit & Datenschutz:**
    *   **Keine Speicherung:** Dein Passwort wird **niemals** auf dem Server gespeichert (weder in einer Datenbank noch in Logs).
    *   **Durchleitung:** Das Passwort wird nur für den Moment des Logins an die DHBW-Server weitergereicht.
    *   **Session:** Nach dem Login wird lediglich ein temporäres Session-Token (Cookie) im Arbeitsspeicher gehalten, um die Noten abzurufen.
    *   **Open Source:** Der gesamte Quellcode ist hier einsehbar.

## Features

*   ✅ **Dashboard:** Schneller Überblick über die letzten Noten und den aktuellen GPA.
*   ✅ **Prüfungsliste:** Alle Prüfungen eines Semesters übersichtlich aufgelistet.
*   ✅ **Details:** Einsicht in Teilprüfungen und Versuche (die in Dualis oft in Popups versteckt sind).
*   ✅ **Dark Mode:** Augenschonendes Design für nächtliche Noten-Checks.

