# プログラム設計書: PICO2 自動販売機シミュレーター

## 1. システム概要
本システムは、PC（Flask Webサーバー）と Raspberry Pi Pico2（物理デバイス）をシリアル通信で連携させ、Webブラウザから操作・監視できる自動販売機シミュレーターです。

### 主な機能
- **商品管理**: SQLiteデータベースによる商品の価格・在庫管理。
- **LED制御**: Pico2上のLED（緑4つ、赤4つ）の状態制御（点灯、消灯、点滅）。
- **投入金額シミュレーション**: Web UIからのコイン投入と、金額に応じた購入可能表示（緑LED点灯）。
- **リアルタイム通知**: Pico2からのボタン押下イベント等をSSE (Server-Sent Events) を用いてブラウザに即時反映。
- **購入処理**: 投入金額が足りている状態で物理ボタン（またはWeb UI）を操作すると、在庫が減り金額がリセットされる。

## 2. システムアーキテクチャ

```mermaid
graph TD
    Browser[Web Browser (JS)] <--> Flask[Flask Web Server (Python)]
    Flask <--> DB[(SQLite)]
    Flask <--> Serial[Serial Communication]
    Serial <--> Pico2[Raspberry Pi Pico2]
```

### コンポーネント構成
- **フロントエンド**: HTML5, CSS3, JavaScript (Vanilla JS)。
- **バックエンド**: Python 3, Flask。
- **データベース**: SQLite3。
- **デバイス制御**: `pyserial` を用いた非同期通信。

## 3. データベース設計 (SQLite)

### `products` テーブル
| カラム名 | 型 | 説明 |
| :--- | :--- | :--- |
| `id` | INTEGER | プライマリキー、自動増分 |
| `name` | TEXT | 商品名 |
| `price` | INTEGER | 価格 |
| `stock` | INTEGER | 在庫数 |
| `max_stock` | INTEGER | 在庫最大数 |
| `capacity` | INTEGER | 格納可能数 |
| `image_url` | TEXT | 商品画像のURL |

## 4. API 仕様 (Web)

### 商品関連
- `GET /api/products`: 全商品情報の取得。
- `POST /api/products/<id>/purchase`: 指定商品の購入処理（在庫を1減らす）。

### LED・デバイス関連
- `POST /api/led/set`: 単一LEDの制御。
- `POST /api/led/bulk`: 8つのLEDの一括制御。
- `POST /api/req/sta`: Pico2へ状態通知（LED/BTN）を要求。
- `GET /stream`: SSEによるデバイスからのメッセージストリーム。

## 5. シリアル通信プロトコル (PC ↔ Pico2)
詳細は `Interface.md` に準拠。

- **フレーミング**: LF (`\n`) 終端、UTF-8。
- **メッセージ形式**: `[TAG]:CMD:PAYLOAD`
- **LED 順序**: 緑0, 緑1, 緑2, 緑3, 赤0, 赤1, 赤2, 赤3 (計8つ)

### 主要コマンド例
- `[PC]:LED:SET:<id>:<ctrl>`: 個別設定
- `[PC]:LED:<8chars>`: 一括設定（`0`:消灯, `1`:点灯, `2`:点滅, `-`:維持）
- `[PI]:NTF:BTNx:<STATE>`: ボタンイベント通知

## 6. 主要シーケンス

### 商品購入フロー (物理ボタン経由)
1. ユーザーがWeb UIでコインを投入（`totalAmount` が増加）。
2. Web UIが `totalAmount` と各商品の `price` を比較し、購入可能な商品の緑LEDを点灯させるコマンドを送信。
3. ユーザーが Pico2 の物理ボタンを押下。
4. Pico2 から `[PI]:NTF:BTNx:OFF`（ボタンが離された）が送信される。
5. Flask が受信し、SSE 経由でブラウザへ通知。
6. ブラウザ側 JS が通知を受け取り、条件（金額・在庫）を満たしていれば `/api/products/<id>/purchase` を叩く。
7. DB の在庫が更新され、UI が再描画される。

## 7. ファイル構成
- `app.py`: メインアプリケーションロジック、API実装、DB初期化。
- `pico_serial.py`: シリアル通信クライアント、プロトコル解析。
- `static/main.js`: フロントエンドロジック（UI制御、SSE受信）。
- `templates/index.html`: UIレイアウト。
- `Interface.md`: 通信仕様詳細。
- `products.db`: データベースファイル。

## 8. 画像アセットの管理
画像データは外部サーバーではなく、サーバー内の以下のディレクトリに配置します。
- **配置場所**: `static/images/`
- **ファイル名規則**:
  - `apple.png`: りんご
  - `banana.png`: バナナ
  - `orange.png`: オレンジ
  - `melon.png`: メロン

※データベース（`products.db`）が既に存在する場合、`app.py` の初期データ変更を反映させるには、既存の `products.db` を削除してからサーバーを再起動してください。
