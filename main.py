# ✅ SQLite 改 PostgreSQL 並加入墼上、得點圈安打率與個人區間紀錄查詢

from flask import Flask, render_template, request, redirect
import psycopg2
import os
from datetime import date
from urllib.parse import urlparse

app = Flask(__name__)

# ✅ 連接 PostgreSQL（使用 DATABASE_URL）
def get_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("❌ 沒有設定 DATABASE_URL 環境變數")
    result = urlparse(db_url)
    return psycopg2.connect(
        dbname=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )

# ✅ 初始化資料表
def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS players (
            number TEXT PRIMARY KEY,
            name TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS records (
            id SERIAL PRIMARY KEY,
            number TEXT,
            name TEXT,
            date TEXT,
            average REAL,
            result TEXT,
            has_runner TEXT,
            rbi INTEGER
        )''')
        conn.commit()

# ✅ 載入球員
def load_players():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT number, name FROM players ORDER BY number")
        return [{'number': row[0], 'name': row[1]} for row in c.fetchall()]

# ✅ 儲存球員
def save_player(player):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO players (number, name) VALUES (%s, %s)", (player['number'], player['name']))
        conn.commit()

# ✅ 載入打擊紀錄
def load_records():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, number, name, date, average, result, has_runner, rbi FROM records")
        return [{
            'id': row[0],
            'number': row[1],
            'name': row[2],
            'date': row[3],
            'average': row[4],
            'result': row[5],
            'has_runner': row[6] or '',
            'rbi': row[7]
        } for row in c.fetchall()]

# ✅ 儲存打擊紀錄
def save_record(record):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO records (number, name, date, average, result, has_runner, rbi)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                     (record['number'], record['name'], record['date'], record['average'],
                      record['result'], record['has_runner'], record['rbi']))
        conn.commit()

# ✅ 刪除紀錄
def delete_record_by_index(record_id):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM records WHERE id = %s", (record_id,))
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

@app.route('/records')
def personal_record_form():
    players = load_players()
    return render_template('personal_form.html', players=players)

@app.route('/records/result', methods=['POST'])
def personal_record_result():
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    number = request.form['player_number']
    records = sorted(
        [r for r in load_records() if r['number'] == number and start_date <= r['date'] <= end_date],
        key=lambda r: r['date'], reverse=True
    )
    player = next((p for p in load_players() if p['number'] == number), None)
    return render_template('personal_result.html', records=records, player=player, start=start_date, end=end_date)

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
                if row['result'] not in ['保送']:
                    total_at_bats += 1
                if row['result'] in hit_results:
                    total_hits += 1

        if result not in ['保送']:
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
    # ✅ 僅算安打與保送為合法上壘
    on_base_results = hit_results + ['保送']

    stats = []
    for p in players:
        number = p['number']
        name = p['name']
        at_bats = hits = walks = on_base = total_rbi = total_bases = 0
        runner_on_any_base_hits = 0
        runner_on_any_base_at_bats = 0
        risp_specific_hits = 0
        risp_specific_at_bats = 0

        for r in records:
            if r['number'] != number:
                continue
            result = r['result']
            has_runner = (r['has_runner'] or '').strip()

            is_ab = result not in ['保送']
            is_hit = result in hit_results

            if is_ab and (has_runner == '一壘有人' or has_runner == '得點圈有人'):
                runner_on_any_base_at_bats += 1
                if is_hit:
                    runner_on_any_base_hits += 1

            if is_ab and has_runner == '得點圈有人':
                risp_specific_at_bats += 1
                if is_hit:
                    risp_specific_hits += 1

            if is_ab:
                at_bats += 1
                if is_hit:
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
            except (ValueError, TypeError):
                pass

        average = round(hits / at_bats, 3) if at_bats > 0 else 0.000
        obp = round(on_base / (at_bats + walks), 3) if (at_bats + walks) > 0 else 0.000
        slg = round(total_bases / at_bats, 3) if at_bats > 0 else 0.000
        runner_avg = round(runner_on_any_base_hits / runner_on_any_base_at_bats, 3) if runner_on_any_base_at_bats > 0 else 0.000
        risp_avg = round(risp_specific_hits / risp_specific_at_bats, 3) if risp_specific_at_bats > 0 else 0.000

        stats.append({
            'number': number,
            'name': name,
            'at_bats': at_bats,
            'hits': hits,
            'average': f"{average:.3f}",
            'obp': f"{obp:.3f}",
            'slg': f"{slg:.3f}",
            'rbi': total_rbi,
            'runner_avg': f"{runner_avg:.3f}",
            'risp_avg': f"{risp_avg:.3f}"
        })

    return render_template('summary.html', stats=stats)


# ✅ 啟動前建立資料表
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
