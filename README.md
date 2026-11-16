# 投稿審查系統

期中個人專題
## 功能

- 作者：查看自己的投稿、新增、修改、刪除編輯中的稿件、送出投稿。
- 編輯：查看待審清單與全文、通過或退回稿件。
- 狀態：編輯中（editing）、審查中（reviewing）、已通過（approved）。
- 退回後可修改再送出；審查中與已通過的稿件無法修改或刪除。
- PostgreSQL 保存所有稿件，關閉網站後資料仍保留。

## 安裝與執行

需要 Python、PostgreSQL，以及可連線的資料庫帳號。

在這份 README 所在資料夾開啟終端機：

```powershell
python -m pip install -r requirements.txt
python app.py
```

保持終端機開啟，在瀏覽器進入 **http://localhost:5000**。Windows 也可使用 start.bat。

網站首頁會進入連線設定，請填寫你自己的 PostgreSQL 設定：

| 設定 | 預設值 |
| --- | --- |
| 伺服器 | localhost |
| 連接埠 | 5432 |
| 資料庫 | submission_review |
| 帳號 | postgres |
| 密碼 | 安裝 PostgreSQL 時設定的密碼 |

已有資料庫時按「連線並開啟系統」。第一次使用可按「首次建立資料庫」，帳號需要 CREATEDB 權限。程式會初始化兩張資料表與三個展示身分，不會清空既有稿件。

原視窗版使用相同資料表，網站連到相同資料庫即可讀取原本稿件。

結束 demo 時回到終端機按 Ctrl+C。重啟後需要重新輸入資料庫連線設定；資料庫內容仍保留。

如果 5000 已被其他程式使用，可在 PowerShell 執行：

```powershell
$env:PORT = "5001"
python app.py
```

此時開啟 http://localhost:5001。示範時建議保持預設 5000。

## 操作流程

1. 選「作者一」，按「切換身分」。
2. 新增稿件並儲存，清單顯示編輯中。
3. 送出投稿，狀態改為審查中。
4. 切換編輯，點「查看並審查」，閱讀後按「退回修改」。
5. 切回作者，修改並儲存，再次送出。
6. 編輯通過，切回作者確認已通過。
7. 另建一篇編輯中稿件測試刪除。
8. 切到作者二，確認看不到作者一稿件。
9. 重啟網站並重新連線，確認資料保留。

## 專案結構

```text
app.py              Flask 路由、接收表單、角色切換與頁面回應
database.py         PostgreSQL 存取、交易與狀態規則
schema.sql          使用者與稿件資料表、主鍵外鍵與限制
requirements.txt    Python 套件
start.bat           Windows 啟動入口
templates/          Jinja HTML 頁面
static/style.css    網頁樣式
操作說明.md         詳細操作與排錯
demo準備.md         展示順序與程式解釋
```

## 路由

| 網址 | 方法 | 功能 |
| --- | --- | --- |
| /setup | GET / POST | 連線頁、初始化資料庫 |
| / | GET | 作者投稿清單或編輯待審清單 |
| /identity | POST | 切換展示身分 |
| /articles/new | GET / POST | 新增稿件 |
| /articles/編號 | GET / POST | 查看全文或儲存修改 |
| /articles/編號/submit | POST | 送出投稿 |
| /articles/編號/delete | POST | 刪除編輯中稿件 |
| /articles/編號/approve | POST | 通過審查 |
| /articles/編號/return | POST | 退回修改 |

## 資料庫設計

review_users 存使用者與角色。review_articles 存稿件，author_id 外鍵對應作者，並保存類別、標題、內容、狀態與時間。

SQL 使用參數傳入資料，更新及刪除時再次檢查角色、作者及狀態；每次操作使用交易，失敗會回滾。表單具 CSRF token，HTML 由 Jinja 自動跳脫。

在 pgAdmin 的 submission_review 資料庫執行：

```sql
SELECT a.id, u.display_name AS author, a.category, a.title, a.status
FROM review_articles a
JOIN review_users u ON u.id = a.author_id
ORDER BY a.id;
```

## 展示版範圍

身分透過選單切換，未實作帳號登入驗證。PostgreSQL 密碼只保留在伺服器記憶體，不寫入檔案或瀏覽器 cookie。此版本供 localhost 個人電腦 demo 使用，資料庫設定供同一伺服器的瀏覽器共用。

GitHub 提交原始碼、templates、static、schema.sql 和說明文件即可。不要提交密碼、虛擬環境或 PostgreSQL 資料目錄。
