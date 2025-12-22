import requests
import re
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, url_for, session, flash
from urllib.parse import quote, unquote

import os

app = Flask(__name__)
# Sicherheit: Key aus Umgebungsvariable laden oder Fallback für lokal
app.secret_key = os.environ.get('SECRET_KEY', 'lokaler_geheimer_schluessel_bitte_aendern')

# Basis-URLs
BASE_URL = "https://dualis.dhbw.de/scripts/mgrqispi.dll"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 1. Login Request an Dualis senden
        s = requests.Session()
        
        # Startseite abrufen, um Formular-Daten zu extrahieren
        # Wir nutzen direkt die URL, auf die weitergeleitet wird (siehe debug_start_page.html)
        start_url = "https://dualis.dhbw.de/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=EXTERNALPAGES&ARGUMENTS=-N000000000000001,-N000324,-Awelcome"
        
        try:
            r_start = s.get(start_url, headers=HEADERS)
            soup_start = BeautifulSoup(r_start.text, 'html.parser')
            login_form = soup_start.find('form', {'id': 'cn_loginForm'})
            
            if not login_form:
                # Fallback: Falls wir immer noch auf einer Redirect-Seite sind
                if "Sie werden zur Startseite weitergeleitet" in r_start.text:
                     # Link aus dem Redirect extrahieren
                     redirect_link = soup_start.find('a', href=True, text=re.compile("Startseite"))
                     if redirect_link:
                         start_url = "https://dualis.dhbw.de" + redirect_link['href']
                         r_start = s.get(start_url, headers=HEADERS)
                         soup_start = BeautifulSoup(r_start.text, 'html.parser')
                         login_form = soup_start.find('form', {'id': 'cn_loginForm'})

            if not login_form:
                print(f"Error: Could not find login form on start page. Status Code: {r_start.status_code}")
                # Debug: Startseite speichern
                with open('debug_start_page.html', 'w', encoding='utf-8') as f:
                    f.write(r_start.text)
                
                flash('Verbindungsfehler: Login-Formular nicht gefunden (siehe Terminal/Debug-File).')
                return render_template('login.html')

            # Payload dynamisch aufbauen
            payload = {}
            for input_tag in login_form.find_all('input'):
                name = input_tag.get('name')
                value = input_tag.get('value', '')
                if name:
                    payload[name] = value
            
            # Benutzerdaten eintragen
            payload['usrname'] = username
            payload['pass'] = password
            
            # Action URL ermitteln
            action = login_form.get('action')
            if action.startswith('/'):
                post_url = "https://dualis.dhbw.de" + action
            else:
                post_url = "https://dualis.dhbw.de/scripts/" + action # Fallback

            # Referer Header setzen (wichtig!)
            post_headers = HEADERS.copy()
            post_headers['Referer'] = start_url

            print(f"Sending login POST to {post_url}")
            # print(f"Payload: {payload}") # Debug (Passwort nicht loggen!)

            r = s.post(post_url, data=payload, headers=post_headers)
            
            # Debug: URL nach Login
            print(f"URL after login: {r.url}")
            print("Response Headers:", r.headers)
            
            # 2. Prüfen ob Login erfolgreich
            
            # Parse response for Meta Refresh or JS Redirect
            soup_response = BeautifulSoup(r.text, 'html.parser')

            # Check for HTTP Refresh Header (nicht im HTML, sondern im HTTP-Header)
            if 'Refresh' in r.headers:
                refresh_header = r.headers['Refresh']
                print(f"Found Refresh Header: {refresh_header}")
                # Format oft: "0; url=..."
                # Case-insensitive split
                match = re.search(r'url=([^;]+)', refresh_header, re.IGNORECASE)
                if match:
                    redirect_url = match.group(1).strip()
                    if redirect_url.startswith('/'):
                        redirect_url = "https://dualis.dhbw.de" + redirect_url
                    
                    print(f"Following Refresh Header to: {redirect_url}")
                    r = s.get(redirect_url, headers=HEADERS)
                    soup_response = BeautifulSoup(r.text, 'html.parser')

            # Check for Meta Refresh (Redirect via HTML Header)
            soup_response = BeautifulSoup(r.text, 'html.parser')
            
            # Check for Meta Refresh (Redirect via HTML Header)
            meta_refresh = soup_response.find('meta', attrs={'http-equiv': re.compile("refresh", re.I)})
            if meta_refresh:
                content = meta_refresh.get('content', '')
                if 'url=' in content.lower():
                    redirect_url = content.split('url=')[-1].strip()
                    if redirect_url.startswith('/'):
                        redirect_url = "https://dualis.dhbw.de" + redirect_url
                    
                    print(f"Following Meta Refresh to: {redirect_url}")
                    r = s.get(redirect_url, headers=HEADERS)
                    soup_response = BeautifulSoup(r.text, 'html.parser') # Update soup

            # Check for JavaScript Redirect (window.location.href = ...)
            # Often used when Meta Refresh is not used
            scripts = soup_response.find_all('script')
            for script in scripts:
                if script.string and 'window.location.href' in script.string:
                    match = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", script.string)
                    if match:
                        redirect_url = match.group(1)
                        if redirect_url.startswith('/'):
                            redirect_url = "https://dualis.dhbw.de" + redirect_url
                        print(f"Following JS Redirect to: {redirect_url}")
                        r = s.get(redirect_url, headers=HEADERS)
                        break

            # Wir prüfen zuerst, ob wir wieder auf der Login-Seite gelandet sind
            if 'name="usrname"' in r.text or 'Anmeldung' in r.text:
                print("Login failed: Login form detected in response.")
                # Debug: Response speichern
                with open('login_response_debug.html', 'w', encoding='utf-8') as f:
                    f.write(r.text)
                flash('Login fehlgeschlagen. Benutzername oder Passwort falsch.')
                return render_template('login.html')

            # Wir suchen nach der Session ID im Response
            # Wir ignorieren die "öffentliche" Session ID 000000000000001
            matches = re.findall(r'ARGUMENTS=-N(\d{15,})', r.text)
            
            session_id = None
            for m in matches:
                if m != '000000000000001':
                    session_id = m
                    break
            
            # Fallback: Suche im Refresh Header oder Location Header falls vorhanden
            if not session_id and 'ARGUMENTS=-N' in r.url:
                 match = re.search(r'ARGUMENTS=-N(\d{15,})', r.url)
                 if match and match.group(1) != '000000000000001':
                     session_id = match.group(1)

            if session_id:
                print(f"Login successful. Session ID: {session_id}")
                session['dualis_id'] = session_id
                session['dualis_cookies'] = s.cookies.get_dict() # Cookies speichern!
                return redirect(url_for('dashboard'))
            else:
                print("Login failed: No valid session ID found.")
                # Debug: Response speichern (als Bytes, um Encoding-Fehler zu vermeiden)
                with open('login_response_debug.html', 'wb') as f:
                    f.write(r.content)
                flash('Login fehlgeschlagen. Unbekannter Fehler (siehe Terminal).')
                return render_template('login.html')
                
        except Exception as e:
            flash(f'Verbindungsfehler zu Dualis: {str(e)}')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'dualis_id' not in session:
        return redirect(url_for('login'))

    session_id = session['dualis_id']
    s = requests.Session()
    
    # Cookies wiederherstellen
    if 'dualis_cookies' in session:
        s.cookies.update(session['dualis_cookies'])

    # 3. Noten abrufen (Leistungsübersicht)
    # Wir versuchen den Link dynamisch zu finden, da sich die Argumente ändern können
    # Zuerst die Startseite laden
    start_url = f"https://dualis.dhbw.de/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=STARTPAGE_DISPATCH&ARGUMENTS=-N{session_id}"
    r_start = s.get(start_url, headers=HEADERS)
    soup_start = BeautifulSoup(r_start.text, 'html.parser')
    
    # Suche nach dem Link "Leistungsübersicht" (meist ID link000310)
    grades_url = None
    
    # Versuch 1: Über ID (am sichersten)
    link_element = soup_start.find(id='link000310')
    if link_element:
        a_tag = link_element.find('a')
        if a_tag and a_tag.get('href'):
            grades_url = "https://dualis.dhbw.de" + a_tag['href']
            
    # Versuch 2: Über Text
    if not grades_url:
        a_tag = soup_start.find('a', string=re.compile("Leistungsübersicht|Prüfungsergebnisse"))
        if a_tag and a_tag.get('href'):
            grades_url = "https://dualis.dhbw.de" + a_tag['href']
            
    if grades_url:
        print(f"Fetching grades from: {grades_url}")
        r = s.get(grades_url, headers=HEADERS)
    else:
        print("Warning: Could not find grades link dynamically. Using fallback.")
        # Fallback: URL zusammenbauen (wie bisher, aber mit Risiko)
        args = f"-N{session_id},-N000310,-N0,-N000000000000000,-N000000000000000,-N000000000000000,-N0,-N000000000000000"
        params = {
            'APPNAME': 'CampusNet',
            'PRGNAME': 'STUDENT_RESULT',
            'ARGUMENTS': args
        }
        r = s.get(BASE_URL, params=params, headers=HEADERS)
    
    # 4. Parsing der Noten (Der spannende Teil!)
    soup = BeautifulSoup(r.content, 'html.parser')
    
    # Wir suchen die Tabelle mit class "students_results"
    table = soup.find('table', {'class': 'students_results'})
    
    modules = []
    gpa_data = {'gesamt': '?', 'hauptfach': '?'}

    if table:
        # GPA auslesen (steht ganz unten in einer separaten kleinen Tabelle im gleichen Div)
        gpa_table = soup.find_all('table', {'class': 'students_results'})
        if len(gpa_table) > 1: # Die zweite Tabelle ist oft die GPA Tabelle
            rows = gpa_table[1].find_all('tr')
            for row in rows:
                if "Gesamt-GPA" in row.text:
                    gpa_data['gesamt'] = row.find_all('th')[1].text.strip()
                if "Hauptfach-GPA" in row.text:
                    gpa_data['hauptfach'] = row.find_all('th')[1].text.strip()

        # Noten auslesen
        rows = table.find_all('tr')
        current_category = "Allgemein"
        
        for row in rows:
            # Kategorien erkennen (z.B. "Künstliche Intelligenz")
            if 'level01' in row.get('class', []) or 'level02' in row.get('class', []):
                text = row.text.strip()
                if "Summe" not in text and text: # Keine Summenzeilen als Kategorie
                    current_category = text

            # Echte Notenzeilen haben meist 'tbdata' tds
            cols = row.find_all('td', {'class': 'tbdata'})
            if len(cols) >= 5:
                # Spalten laut deinem HTML:
                # 0: Code (T4INF1001)
                # 1: Name (Mathematik I)
                # 3: Credits
                # 4: Note
                # 5: Status Icon
                
                module_code = cols[0].text.strip()
                module_name = cols[1].text.strip()
                credits = cols[3].text.strip()
                grade = cols[4].text.strip()
                
                # Status checken (Bestanden/Offen)
                status = "unknown"
                img = cols[5].find('img')
                if img:
                    if "pass" in img['src']: status = "bestanden"
                    elif "open" in img['src']: status = "offen"
                    elif "fail" in img['src']: status = "nicht bestanden"

                # Nur echte Module aufnehmen (keine leeren Zeilen)
                if module_name:
                    # Detail-Link extrahieren (Javascript Popup)
                    # <a href="javascript:popUp('...ARGUMENTS=-N123,-N456...')">
                    detail_link = None
                    script_link = cols[5].find('script')
                    if script_link and script_link.string:
                        match = re.search(r"popUp\('([^']+)'\)", script_link.string)
                        if match:
                            detail_link = match.group(1)
                    
                    # Alternativ: Manchmal ist der Link direkt im Namen oder Code
                    if not detail_link:
                         a_tag = cols[0].find('a') # Code Spalte
                         if a_tag and 'popUp' in a_tag.get('href', ''):
                             match = re.search(r"popUp\('([^']+)'\)", a_tag['href'])
                             if match:
                                 detail_link = match.group(1)

                    modules.append({
                        'code': module_code,
                        'name': module_name,
                        'credits': credits,
                        'grade': grade,
                        'status': status,
                        'category': current_category,
                        'detail_link': detail_link # Speichern für Detailansicht
                    })

    # Name des Studenten auslesen
    # Versuch 1: Über ID loginDataName (genauer)
    student_name = "Student"
    login_name_span = soup.find('span', {'id': 'loginDataName'})
    if login_name_span:
        # Text ist oft "Name: Max Mustermann"
        text = login_name_span.text
        if "Name:" in text:
            student_name = text.split("Name:")[-1].strip()
        else:
            student_name = text.strip()
    else:
        # Versuch 2: Über h1 (Fallback)
        welcome_text = soup.find('h1')
        if welcome_text:
            student_name = welcome_text.text.replace('Studienergebnisse von: ', '').strip()

    # Cookies aktualisieren
    session['dualis_cookies'] = s.cookies.get_dict()

    return render_template('dashboard.html', modules=modules, student=student_name, gpa=gpa_data)

@app.route('/exams')
def exams():
    if 'dualis_id' not in session:
        return redirect(url_for('login'))

    session_id = session['dualis_id']
    s = requests.Session()
    if 'dualis_cookies' in session:
        s.cookies.update(session['dualis_cookies'])

    # 1. URL für Prüfungsergebnisse finden (ähnlich wie bei Dashboard)
    # Wir suchen nach Link ID 000307 (Prüfungsergebnisse)
    start_url = f"https://dualis.dhbw.de/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=STARTPAGE_DISPATCH&ARGUMENTS=-N{session_id}"
    
    # Wenn wir schon eine URL haben (z.B. Semesterwechsel), nutzen wir die
    target_url = request.args.get('url')
    
    if not target_url:
        # Link dynamisch suchen
        r_start = s.get(start_url, headers=HEADERS)
        soup_start = BeautifulSoup(r_start.text, 'html.parser')
        
        link_element = soup_start.find(id='link000307')
        if link_element:
            a_tag = link_element.find('a')
            if a_tag and a_tag.get('href'):
                target_url = "https://dualis.dhbw.de" + a_tag['href']
        
        if not target_url:
             # Fallback
             target_url = f"https://dualis.dhbw.de/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=COURSERESULTS&ARGUMENTS=-N{session_id},-N000307,"

    # Wenn Semester übergeben wurde, müssen wir die URL anpassen
    # Das Formular sendet POST, aber wir können auch GET Parameter manipulieren oder den Link direkt bauen
    # Der Semester-Wechsel ist im HTML ein onchange JS: reloadpage.createUrlAndReload(..., '-N'+this.value)
    # Das bedeutet, das letzte Argument wird durch das Semester ersetzt.
    
    semester_arg = request.args.get('semester')
    if semester_arg:
        # Wir müssen die URL manipulieren, um das Semester Argument zu setzen
        # Die URL endet oft auf ein Komma oder ein Argument.
        # Wir bauen die URL am besten neu auf, wenn wir die Basis kennen, oder wir nutzen den POST Request wie im Formular
        # Einfacher: Wir simulieren den Link, den das JS bauen würde.
        # createUrlAndReload('/scripts/mgrqispi.dll','CampusNet','COURSERESULTS','470705467050617','000307','-N'+this.value)
        target_url = f"https://dualis.dhbw.de/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=COURSERESULTS&ARGUMENTS=-N{session_id},-N000307,-N{semester_arg}"

    print(f"Fetching exams from: {target_url}")
    r = s.get(target_url, headers=HEADERS)
    
    # Update URL to the actual one (in case of redirects or if we constructed it slightly differently)
    final_url = r.url
    print(f"Final Exams URL: {final_url}")

    soup = BeautifulSoup(r.content, 'html.parser')

    # 2. Semester-Auswahl parsen
    semesters = []
    select = soup.find('select', {'id': 'semester'})
    selected_semester = None
    selected_semester_value = ""
    if select:
        for option in select.find_all('option'):
            val = option.get('value')
            text = option.text.strip()
            is_selected = option.get('selected') is not None
            semesters.append({'value': val, 'text': text, 'selected': is_selected})
            if is_selected:
                selected_semester = text
                selected_semester_value = val

    # 3. Tabelle parsen
    exams_list = []
    # Try finding table with 'list' class
    table = soup.find('table', {'class': 'list'}) 
    if not table:
        table = soup.find('table', {'class': 'nb list'})
    
    # Cookies aktualisieren (falls sich was geändert hat)
    session['dualis_cookies'] = s.cookies.get_dict()
    
    if table:
        rows = table.find_all('tr')
        for row in rows:
            # Skip header rows (often contain th or specific classes)
            if row.find('th'):
                continue
            
            # WICHTIG: Wir müssen alle Spalten nehmen, auch tbdata_numeric!
            cols = row.find_all('td')
            
            # Spalten: 0: Nr, 1: Name, 2: Endnote, 3: Credits, 4: Status, 5: Details, 6: leer
            if len(cols) >= 5:
                code = cols[0].text.strip()
                name = cols[1].text.strip()
                
                # Filter out header-like rows that might be using td instead of th
                if code == "Nr." and name == "Name":
                    continue

                grade = cols[2].text.strip()
                credits = cols[3].text.strip()
                status = cols[4].text.strip()
                
                # Detail Link
                detail_link = None
                if len(cols) > 5:
                    # 1. Versuch: Script Tag (dl_popUp oder popUp) - BEVORZUGT, da dies das echte Verhalten ist
                    script_link = cols[5].find('script')
                    if script_link and script_link.string:
                        # Suche nach dl_popUp oder popUp
                        match = re.search(r"(?:dl_)?popUp\('([^']+)'\)", script_link.string)
                        if match:
                            detail_link = match.group(1)

                    # 2. Versuch: Direktes href im a-Tag (Fallback)
                    if not detail_link:
                        a_tag = cols[5].find('a')
                        if a_tag and a_tag.get('href') and not a_tag['href'].startswith('javascript') and not a_tag['href'] == '#':
                            detail_link = a_tag['href']
                    
                    # 3. Versuch: a-Tag mit popUp im href (Fallback 2)
                    if not detail_link:
                         a_tag = cols[5].find('a')
                         if a_tag and 'popUp' in a_tag.get('href', ''):
                             match = re.search(r"popUp\('([^']+)'\)", a_tag['href'])
                             if match:
                                 detail_link = match.group(1)
                             
                if name:
                    exams_list.append({
                        'code': code,
                        'name': name,
                        'grade': grade,
                        'credits': credits,
                        'status': status,
                        'detail_link': detail_link
                    })

    return render_template('exams.html', semesters=semesters, exams=exams_list, selected_semester=selected_semester, selected_semester_value=selected_semester_value, current_url=final_url)

import html

@app.route('/details')
def details():
    if 'dualis_id' not in session:
        return redirect(url_for('login'))
    
    # Der Link kommt als Query Parameter
    relative_url = request.args.get('url')
    semester_val = request.args.get('semester')
    
    if not relative_url:
        flash('Ungültiger Link für Details.')
        return redirect(url_for('dashboard'))

    # URL Decoding: &amp; zu &
    relative_url = html.unescape(relative_url)

    s = requests.Session()
    if 'dualis_cookies' in session:
        s.cookies.update(session['dualis_cookies'])
    
    full_url = "https://dualis.dhbw.de" + relative_url
    print(f"Fetching details from: {full_url}")
    
    # Check Session ID match
    session_id = session.get('dualis_id', '')
    if f"-N{session_id}" not in full_url:
        print(f"WARNING: Session ID mismatch! Session: {session_id} not in URL.")
    
    # Referer Header setzen
    referer_arg = request.args.get('referer')
    if referer_arg:
        referer_url = unquote(referer_arg)
        referer_url = html.unescape(referer_url) # Auch hier sicherstellen
    else:
        referer_url = f"https://dualis.dhbw.de/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=COURSERESULTS&ARGUMENTS=-N{session_id},-N000307,"
    
    print(f"Using Referer: {referer_url}")
    print(f"Cookies: {s.cookies.get_dict()}")
    
    headers = HEADERS.copy()
    headers['Referer'] = referer_url

    try:
        r = s.get(full_url, headers=headers)
        
        # Cookies aktualisieren
        session['dualis_cookies'] = s.cookies.get_dict()
        
        # DEBUG: Save HTML
        with open('details_debug.html', 'w', encoding='utf-8') as f:
            f.write(r.text)
            
        soup = BeautifulSoup(r.content, 'html.parser')
        
        # Titel extrahieren (z.B. "T4INF2001 Mathematik III")
        title_tag = soup.find('h1')
        title = title_tag.text.strip() if title_tag else "Details"
        
        # Tabelle parsen
        # Die Struktur ist komplexer (verschachtelte Tabellen oder Zeilen mit colspan)
        # Wir suchen nach Zeilen mit class 'tbdata' oder 'level01'/'level02'
        
        details = []
        main_table = soup.find('table', {'class': 'tb'})
        
        if main_table:
            rows = main_table.find_all('tr')
            current_attempt = ""
            
            for row in rows:
                # Versuch (z.B. "Versuch 1")
                # Check row class OR cell class
                if 'level01' in row.get('class', []) or row.find('td', {'class': 'level01'}):
                    text = row.text.strip()
                    if "Versuch" in text:
                        current_attempt = text
                
                # Teilprüfung Name (z.B. "Angewandte Mathematik")
                if 'level02' in row.get('class', []) or row.find('td', {'class': 'level02'}):
                    # Oft colspan=8
                    text = row.text.strip()
                    if text and "Gesamt" not in text:
                        details.append({
                            'type': 'header',
                            'text': text
                        })
                
                # Echte Datenzeile (Semester, Prüfungsart, Datum, Note, Status)
                cols = row.find_all('td', {'class': 'tbdata'})
                
                # Fall 1: Normale Zeile (ca. 5 Spalten)
                if len(cols) >= 4 and cols[0].text.strip():
                    semester = cols[0].text.strip()
                    exam_type = cols[1].text.strip()
                    date = cols[2].text.strip()
                    grade = cols[3].text.strip()
                    
                    status = ""
                    if len(cols) > 4:
                        img = cols[4].find('img')
                        if img:
                            if "pass" in img['src']: status = "bestanden"
                            elif "fail" in img['src']: status = "nicht bestanden"
                    
                    details.append({
                        'type': 'exam',
                        'semester': semester,
                        'exam_type': exam_type,
                        'date': date,
                        'grade': grade,
                        'status': status,
                        'attempt': current_attempt,
                        'is_partial': False
                    })
                
                # Fall 2: Teilprüfung (eingerückt, erste Spalte leer/colspan)
                # Struktur: [Empty/Colspan], [Name], [Empty], [Grade], ...
                elif len(cols) >= 4 and not cols[0].text.strip() and cols[1].text.strip():
                     # Das ist wahrscheinlich eine Teilnote (z.B. "BWL")
                     part_name = cols[1].text.strip()
                     part_grade = cols[3].text.strip()
                     
                     details.append({
                        'type': 'exam',
                        'semester': '', # Teilprüfung hat oft kein eigenes Semester in der Zeile
                        'exam_type': part_name, # Name der Teilprüfung
                        'date': '',
                        'grade': part_grade,
                        'status': 'Teilprüfung',
                        'attempt': current_attempt,
                        'is_partial': True # Markierung für Template
                    })

        return render_template('details.html', title=title, details=details, semester=semester_val)

    except Exception as e:
        print(f"Error fetching details: {e}")
        import traceback
        traceback.print_exc()
        flash('Fehler beim Laden der Details.')
        return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('dualis_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    # host='0.0.0.0' macht es im lokalen Netzwerk verfügbar!
    app.run(debug=True, host='0.0.0.0', port=5000)