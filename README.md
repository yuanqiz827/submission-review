# 投稿審查系統

使用 Python Flask、HTML/CSS 和 PostgreSQL，支援作者投稿、編輯審查、帳密登入與退回意見回饋。

## 啟動

```powershell
python -m pip install -r requirements.txt
python app.py
```

在瀏覽器開啟 http://localhost:5000，保持終端機執行。Windows 也可使用 start.bat。

首次啟動先輸入 PostgreSQL 連線設定。預設 host=localhost、port=5432、資料庫 submission_review、帳號 postgres，密碼請使用自己的資料庫密碼。已有資料庫按「連線並開啟系統」。程式會保留原本資料，新增 password_hash 與 review_feedback 欄位。

之後進入系統登入頁。資料庫連線密碼與下方的網站登入密碼不同。

## 預設展示帳號

| 角色 | 帳號 | 初始密碼 |
| --- | --- | --- |
| 作者一 | author1 | Author123! |
| 作者二 | author2 | Author123! |
| 編輯 | editor1 | Editor123! |

英文大小寫及驚嘆號都要輸入。這些為 localhost 課堂展示用帳號；密碼以 Werkzeug scrypt 雜湊存入 PostgreSQL，不存明文。既有帳號首次升級會設定初始密碼，之後重新連線不會覆蓋已存在的密碼雜湊。

網站不再提供身分切換選單。請先按「登出」，再使用另一個帳號登入。登入後的角色從資料庫取得，不能透過表單指定。未登入不能查看稿件。已連線後，只有編輯能開啟資料庫連線設定；重新設定連線後，所有使用者需再次登入。

## 作者功能

- 只查看自己的投稿清單與完整文章。
- 新增稿件，填寫類別、標題、文章內容，儲存為編輯中。
- 修改或刪除自己的編輯中稿件。
- 送出後變為審查中，不能修改或刪除。
- 查看編輯的最近一次退回意見，修改後重新送出。
- 查看已通過稿件。

## 編輯功能

- 查看待審稿件清單與完整文章。
- 填寫退回意見回饋（1～2000 字，空白不算），再退回修改。
- 退回時，在同一次資料庫操作內儲存意見，將狀態改回編輯中。
- 直接通過稿件，不要求填寫退回意見。

最近一次退回意見顯示於清單及稿件頁，重新送出、通過後仍保留；再次退回時以新的意見取代。此版本未保存每一輪審查的完整歷史。

## 升級既有資料庫

1. 在舊程式的終端機按 Ctrl+C 停止網站。
2. 換成新版程式，重新執行 python app.py。
3. 開網站並重新整理，填原本資料庫設定，按「連線並開啟系統」。
4. 程式自動執行 schema.sql 與初始化帳密，不清空使用者或稿件。
5. 用上方展示帳密登入。原本的 author1、author2 稿件仍屬於同一作者。

不需要重建資料庫。schema.sql 可重複執行；初始密碼雜湊由 database.py 建立。

## 專案結構

```text
app.py                 Flask 路由、登入登出、session、權限檢查與表單
database.py            PostgreSQL 操作、密碼驗證與交易
schema.sql             建表及既有資料庫欄位升級
requirements.txt       Python 套件
start.bat              Windows 啟動入口
templates/             HTML 頁面，含 login.html
static/style.css       網頁樣式
tests/                 登入、權限與回饋測試
操作說明.md            操作及排錯
demo準備.md            展示講稿
```

## 資料表

- review_users：id、username、display_name、role、password_hash。
- review_articles：id、author_id、category、title、content、status、review_feedback、created_at、updated_at。
- author_id 外鍵對應 review_users.id。
- 狀態 editing＝編輯中、reviewing＝審查中、approved＝已通過。

SQL 使用參數化查詢。更新、刪除、審查同時檢查作者或角色及目前狀態，操作失敗時交易回滾。session 只記錄使用者編號及驗證版本，不存密碼或由瀏覽器傳入的角色。表單含 CSRF token，Jinja 自動跳脫使用者文字。

## 測試

```powershell
python -m unittest discover -s tests -v
```

目前 14 項自動測試涵蓋登入、登出、角色越權、作者資料隔離、意見必填、長度、顯示與密碼雜湊驗證。測試使用記憶體替身與模擬資料庫連線，不修改個人資料庫；實際 PostgreSQL 升級及持久化請依操作說明完成驗收。

## 在 pgAdmin 展示

連入 submission_review 後執行：

```sql
SELECT a.id, u.username AS author, a.title, a.status, a.review_feedback
FROM review_articles a
JOIN review_users u ON u.id = a.author_id
ORDER BY a.id;
```

## GitHub 繳交

更新 app.py、database.py、schema.sql、README.md、操作說明.md、demo準備.md，以及完整 templates、static、tests 資料夾。維持正確資料夾路徑。不要提交個人資料庫密碼、虛擬環境或 PostgreSQL 資料目錄。

這是本機課堂展示版；未包含註冊、忘記密碼、寄信或部署功能。
