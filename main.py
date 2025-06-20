from flask import Flask, render_template, request, redirect
import csv
import os
import time
import threading
import requests
from datetime import date

app = Flask(__name__)

PLAYER_FILE = 'players.csv'
RECORD_FILE = 'records.csv'


# 載入球員資料
def load_players():
    if not os.path.exists(PLAYER_FILE):
        return []
    with open(PLAYER_FILE, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


# 儲存新球員
def save_player(player):
    file_exists = os.path.exists(PLAYER_FILE)
    with open(PLAYER_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['number', 'name'])
        if not file_exists:
            writer.writeheader()
        writer.writerow(player)


# 載入打擊紀錄，並加上 ID
def load_records():
    if not os.path.exists(RECORD_FILE):
        return []
    with open(RECORD_FILE, newline='', encoding='utf-8') as f:
        records = list(csv.DictReader(f))
        for i, r in enumerate(records):
            r['id'] = str(i)
        return records


# 儲存單筆打擊紀錄（含 RBI 與壘上）
def save_record(record):
    file_exists = os.path.exists(RECORD_FILE)
    with open(RECORD_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'number', 'name', 'date', 'average', 'result', 'has_runner', 'rbi'
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)


# 刪除指定紀錄
def delete_record_by_index(index):
    records = load_records()
    if 0 <= index < len(records):
        del records[index]
        with open(RECORD_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'number', 'name', 'date', 'average', 'result', 'has_runner', 'rbi'
            ])
            writer.writeheader()
            for r in records:
                del r['id']
                writer.writerow(r)


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
        on_base_results = hit_results + ['保送', '野選', '對手失誤上壘']

        # 統計該球員過去打擊
        total_hits = 0
        total_at_bats = 0
        existing_records = load_records()
        for row in existing_records:
            if row['number'] == number:
                if row['result'] not in ['保送', '高飛犧牲']:
                    total_at_bats += 1
                if row['result'] in hit_results:
                    total_hits += 1

        # 當前這一筆
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

    # records = list(reversed(load_records()))
    # return render_template('batting_form.html', players=players, records=records)


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
        total_bases = 0  # ⭐ 新增

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
                if result == '一壘':
                    total_bases += 1
                elif result == '二壘':
                    total_bases += 2
                elif result == '三壘':
                    total_bases += 3
                elif result == '全壘打':
                    total_bases += 4
                try:
                    total_rbi += int(r['rbi'])
                except:
                    pass

        average = round(hits / at_bats, 3) if at_bats > 0 else 0.000
        obp_denominator = at_bats + walks
        obp = round(on_base / obp_denominator, 3) if obp_denominator > 0 else 0.000
        slg = round(total_bases / at_bats, 3) if at_bats > 0 else 0.000  # ⭐ SLG 計算

        stats.append({
            'number': number,
            'name': name,
            'at_bats': at_bats,
            'hits': hits,
            'average': f"{average:.3f}",
            'obp': f"{obp:.3f}",
            'slg': f"{slg:.3f}",  # ⭐ 加入 SLG 統計
            'rbi': total_rbi
        })

    return render_template('summary.html', stats=stats)




if __name__ == '__main__':

    app.run(host='0.0.0.0', port=81)
