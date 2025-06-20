# ✅ SQLite 儲存版本（改寫自 CSV 版）

from flask import Flask, render_template, request, redirect
import sqlite3
import os
from datetime import date

app = Flask(__name__)

DB_FILE = 'softball.db'

# ✅ 初始化資料庫
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS players (
                        number TEXT PRIMARY KEY,
                        name TEXT
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        number TEXT,
                        name TEXT,
                        date TEXT,
                        average REAL,
                        result TEXT,
                        has_runner TEXT,
                        rbi INTEGER
                    )''')

# ✅ 載入球員資料
def load_players():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT number, name FROM players ORDER BY number asc")
        return [{'number': row[0], 'name': row[1]} for row in c.fetchall()]

# ✅ 儲存新球員
def save_player(player):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO players (number, name) VALUES (?, ?)", (player['number'], player['name']))
        conn.commit()

# ✅ 載入打擊紀錄
def load_records():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, number, name, date, average, result, has_runner, rbi FROM records")
        return [
            {
                'id': row[0],
                'number': row[1],
                'name': row[2],
                'date': row[3],
                'average': f"{row[4]:.3f}",
                'result': row[5],
                'has_runner': row[6],
                'rbi': row[7]
            } for row in c.fetchall()
        ]

# ✅ 儲存打擊紀錄
def save_record(record):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO records (number, name, date, average, result, has_runner, rbi)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (record['number'], record['name'], record['date'], record['average'], record['result'], record['has_runner'], record['rbi']))
        conn.commit()

# ✅ 刪除打擊紀錄
def delete_record_by_index(record_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/players', methods=['GET', 'POST'])
def manage_players():
    if request.method == 'POST':
        number = request.form['player_number']
        name = request.form['player_name']
        players = load_players()
        if any(p['number'] == number for p in players):
            return "⚠️ 此背號已存在！<br><a href='/players'>返回</a>"
        save_player({'number': number, 'name': name})
        return redirect('/players')
    players = load_players()
    return render_template('player_form.html', players=players)

@app.route('/batting', methods=['GET', 'POST'])
def batting_record():
    players = load_players()
    if request.method == 'POST':
        number = request.form['player_number']
        name = next((p['name'] for p in players if p['number'] == number), '未知')
        result = request.form['batting_result']
        game_date = request.form['game_date']
        has_runner = request.form['has_runner']
        rbi = request.form['rbi']

        hit_results = ['一壘', '二壘', '三壘', '全壘打']

        total_hits = 0
        total_at_bats = 0
        existing_records = load_records()
        for row in existing_records:
            if row['number'] == number:
                if row['result'] not in ['保送', '高飛犧牲']:
                    total_at_bats += 1
                if row['result'] in hit_results:
                    total_hits += 1

        if result not in ['保送', '高飛犧牲']:
            total_at_bats += 1
        if result in hit_results:
            total_hits += 1

        average = round(total_hits / total_at_bats, 3) if total_at_bats > 0 else 0.000

        save_record({
            'number': number,
            'name': name,
            'date': game_date,
            'average': average,
            'result': result,
            'has_runner': has_runner,
            'rbi': rbi
        })
        return redirect('/batting')

    records = list(reversed(load_records()))
    today = date.today().isoformat()
    return render_template('batting_form.html', players=players, records=records, today=today)

@app.route('/delete_record/<int:record_id>', methods=['POST'])
def delete_record(record_id):
    delete_record_by_index(record_id)
    return redirect('/batting')

@app.route('/summary')
def summary():
    players = load_players()
    records = load_records()
    hit_results = ['一壘', '二壘', '三壘', '全壘打']
    on_base_results = hit_results + ['保送', '野選', '對手失誤上壘']

    stats = []
    for p in players:
        number = p['number']
        name = p['name']
        at_bats = 0
        hits = 0
        walks = 0
        on_base = 0
        total_rbi = 0
        total_bases = 0

        for r in records:
            if r['number'] == number:
                result = r['result']
                if result not in ['保送', '高飛犧牲']:
                    at_bats += 1
                if result in hit_results:
                    hits += 1
                if result == '保送':
                    walks += 1
                if result in on_base_results:
                    on_base += 1
                if result == '一壘': total_bases += 1
                elif result == '二壘': total_bases += 2
                elif result == '三壘': total_bases += 3
                elif result == '全壘打': total_bases += 4
                try:
                    total_rbi += int(r['rbi'])
                except:
                    pass

        average = round(hits / at_bats, 3) if at_bats > 0 else 0.000
        obp_denominator = at_bats + walks
        obp = round(on_base / obp_denominator, 3) if obp_denominator > 0 else 0.000
        slg = round(total_bases / at_bats, 3) if at_bats > 0 else 0.000

        stats.append({
            'number': number,
            'name': name,
            'at_bats': at_bats,
            'hits': hits,
            'average': f"{average:.3f}",
            'obp': f"{obp:.3f}",
            'slg': f"{slg:.3f}",
            'rbi': total_rbi
        })

    return render_template('summary.html', stats=stats)

# ✅ 啟動前初始化 DB
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
