# 1.データベース
- **プラットフォーム**: Supabase
- **データベース**: PostgreSQL
- **プロジェクト**: vending-manage
- **テーブル**: VendingMachine
- **機能**: Realtime (Postgres Changes) を利用したリアルタイム同期

# 2. データモデル
## 2.1 VendingMachine (自販機)
| フィールド名 | 型 | 説明 |
| :--- | :--- | :--- |
| `id` | UUID | 内部識別子 (主キー) |
| `machine_id` | String | 自販機識別ID (例: VEND-001) |
| `location` | String | 設置場所 |
| `status` | Enum | 現在のステータス |
| `updated_at` | Timestamp | 最終更新日時 |

## 2.2 VendingMachineStatus (ステータス定義)
- `NORMAL`: 通常 (青色バッジ)
- `REQUIRE_REPLENISHMENT`: 補充要求あり (赤色バッジ・点滅アニメーション)
- `COMPLETED`: 補充完了 (緑色バッジ)
