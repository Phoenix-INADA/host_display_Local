"""
Flask app to control Pico2 LEDs asynchronously via serial.
Run: python app.py --port COM3
Requirements: pip install flask pyserial
"""
from flask import Flask, render_template, request, jsonify, Response
import threading
import queue
import json
import argparse
import time
import sqlite3
import os

# import Pico serial helper
from pico_serial import PicoSerial, parse_pi_message

app = Flask(__name__)
DATABASE = 'products.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            stock INTEGER NOT NULL,
            max_stock INTEGER NOT NULL DEFAULT 10,
            capacity INTEGER NOT NULL DEFAULT 10,
            image_url TEXT
        )
    ''')
    
    # 既存テーブルに新カラムがない場合に備えて追加（マイグレーション）
    try:
        db.execute('ALTER TABLE products ADD COLUMN max_stock INTEGER NOT NULL DEFAULT 10')
    except sqlite3.OperationalError:
        pass
    try:
        db.execute('ALTER TABLE products ADD COLUMN capacity INTEGER NOT NULL DEFAULT 10')
    except sqlite3.OperationalError:
        pass

    # データが空の場合のみ初期データを投入
    cursor = db.execute('SELECT COUNT(*) FROM products')
    if cursor.fetchone()[0] == 0:
        initial_products = [
            ('りんご', 150, 10, 20, 20, '/static/images/apple.png'),
            ('バナナ', 100, 20, 30, 30, '/static/images/banana.png'),
            ('オレンジ', 120, 15, 25, 25, '/static/images/orange.png'),
            ('メロン', 500, 5, 10, 10, '/static/images/melon.png')
        ]
        db.executemany('INSERT INTO products (name, price, stock, max_stock, capacity, image_url) VALUES (?, ?, ?, ?, ?, ?)', initial_products)
    
    db.commit()
    db.close()

init_db()

msg_queue = queue.Queue()
serial_client = None
reader_thread = None
reader_stop = threading.Event()

LED_IDS = ['GRN0','GRN1','GRN2','GRN3','RED0','RED1','RED2','RED3']

@app.route('/')
def index():
    return render_template('index.html', led_ids=LED_IDS)

@app.route('/api/products')
def get_products():
    db = get_db()
    cursor = db.execute('SELECT * FROM products')
    products = [dict(row) for row in cursor.fetchall()]
    db.close()
    return jsonify(products)

@app.route('/api/led/set', methods=['POST'])
def led_set():
    if serial_client is None:
        return jsonify({'ok': False, 'error': 'serial not configured'}), 500
    data = request.get_json() or {}
    id_ = data.get('id')
    ctrl = data.get('ctrl')
    if id_ not in LED_IDS or ctrl not in ['0','1','2']:
        return jsonify({'ok': False, 'error': 'bad params'}), 400
    line = f'[PC]:LED:SET:{id_}:{ctrl}\n'
    serial_client.send_raw(line)
    return jsonify({'ok': True})

@app.route('/api/led/bulk', methods=['POST'])
def led_bulk():
    if serial_client is None:
        return jsonify({'ok': False, 'error': 'serial not configured'}), 500
    data = request.get_json() or {}
    payload = data.get('payload','')
    if not isinstance(payload, str) or len(payload) != 8:
        return jsonify({'ok': False, 'error': 'payload must be 8 chars'}), 400
    line = f'[PC]:LED:{payload}\n'
    serial_client.send_raw(line)
    return jsonify({'ok': True})

@app.route('/api/req/sta', methods=['POST'])
def req_sta():
    if serial_client is None:
        return jsonify({'ok': False, 'error': 'serial not configured'}), 500
    data = request.get_json() or {}
    which = data.get('which')
    if which not in ['LED','BTN']:
        return jsonify({'ok': False, 'error': 'which must be LED or BTN'}), 400
    line = f'[PC]:STA:{which}\n'
    serial_client.send_raw(line)
    return jsonify({'ok': True})

@app.route('/stream')
def stream():
    def event_stream():
        # SSE: send json lines
        while True:
            try:
                item = msg_queue.get()
                yield f'data: {json.dumps(item)}\n\n'
            except GeneratorExit:
                break
    return Response(event_stream(), mimetype='text/event-stream')

def reader_loop(client, stop_event):
    while not stop_event.is_set():
        ln = client.read_line()
        if ln:
            parsed = parse_pi_message(ln)
            msg_queue.put(parsed)
        else:
            time.sleep(0.01)

@app.route('/api/products/restock', methods=['POST'])
def restock_products():
    db = get_db()
    # 全商品の在庫をcapacityの値に更新
    db.execute('UPDATE products SET stock = capacity')
    db.commit()
    
    # 更新後の商品情報を取得して返す
    cursor = db.execute('SELECT * FROM products')
    products = [dict(row) for row in cursor.fetchall()]
    db.close()
    return jsonify({'ok': True, 'products': products})

@app.route('/api/products/<int:product_id>/purchase', methods=['POST'])
def purchase_product(product_id):
    db = get_db()
    # 在庫を1減らす（ただし0未満にはしない）
    db.execute('UPDATE products SET stock = MAX(0, stock - 1) WHERE id = ?', (product_id,))
    db.commit()
    
    # 更新後の商品情報を取得して返す
    cursor = db.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = dict(cursor.fetchone())
    db.close()
    return jsonify({'ok': True, 'product': product})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True, help='Serial COM port, e.g., COM3')
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port-flask', type=int, default=5000)
    args = parser.parse_args()

    serial_client = PicoSerial(args.port, baud=args.baud)
    reader_stop.clear()
    reader_thread = threading.Thread(target=reader_loop, args=(serial_client, reader_stop), daemon=True)
    reader_thread.start()

    try:
        app.run(host=args.host, port=args.port_flask, threaded=True)
    finally:
        reader_stop.set()
        if serial_client:
            serial_client.close()
