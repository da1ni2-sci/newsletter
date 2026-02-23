# 鍛碼匠 Fordige 電子報會員資料庫交接文檔

## 1. 系統背景 (Context)
本資料庫存儲了「鍛碼匠 Fordige」官網技術週報的所有訂閱者資訊。系統採用了「雙重訂閱 (Double Opt-in)」機制，僅有驗證通過的會員應被列入發信清單。

## 2. 資料庫連線資訊 (Connection)
最終發信應用（如 newsletter 腳本）應透過以下環境變數連線至 Supabase PostgreSQL：

- **Provider:** Supabase (PostgreSQL)
- **Table Name:** `newsletter_subscribers`
- **Recommended Library:** Prisma ORM 或 `pg` (node-postgres)

## 3. 資料表結構 (Schema Definition)

| 欄位名稱 | 類型 | 說明 |
| :--- | :--- | :--- |
| `id` | SERIAL | 主鍵 |
| `email` | VARCHAR(255) | 會員電子郵件 (唯一值) |
| `identity` | VARCHAR(255) | 會員身份分類 (`developer`, `business`, `hobbyist`) |
| `is_verified` | BOOLEAN | **關鍵欄位**：`true` 代表已通過驗證，可正式發信 |
| `verification_token` | VARCHAR(255) | 驗證用 Token (驗證後通常為 null) |
| `created_at` | TIMESTAMP | 訂閱時間 |
| `updated_at` | TIMESTAMP | 最後更新時間 |

## 4. 最終發信應用集成指南 (Integration)

### 4.1 篩選發信名單
發信應用在執行發信任務前，**必須**過濾出已驗證的用戶。
```sql
-- 範例 SQL
SELECT email, identity FROM newsletter_subscribers WHERE is_verified = true;
```

### 4.2 會員分眾發信 (Segmentation)
為了提升轉換率，建議發信應用根據 `identity` 欄位調整文案語氣：
- **`developer`**: 提供更多 GitHub 連結與實踐代碼。
- **`business`**: 提供 AI 導入成本、SEO 趨勢等商業決策資訊。
- **`hobbyist`**: 提供幽默的科技八卦與科普內容。

### 4.3 異常處理
- **退訂邏輯：** 目前官網後台提供手動刪除功能。若發信應用偵測到退信 (Bounce) 或用戶點擊退訂，應將該紀錄從 `newsletter_subscribers` 中移除或標記。

## 5. 資安注意事項
- **唯讀權限：** 若發信應用僅需讀取資料，建議在 Supabase 另建一個唯讀帳號以符合最小權限原則。
- **個資保護：** 會員 Email 屬於敏感資訊，發信應用的 Log 中應避免明文紀錄完整的 Email 地址。

---
*文檔版本：2026-02-05*
*由「鍛碼匠 Fordige」AI 助手 Yoyo 生成*
