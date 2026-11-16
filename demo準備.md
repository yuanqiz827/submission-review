# Demo 準備

## 展示前

- 開啟 PostgreSQL 服務。
- PowerShell 切到專案資料夾，執行 python app.py。
- 瀏覽器開 http://localhost:5000，完成資料庫連線。
- pgAdmin 開啟 submission_review，準備查詢 review_articles。
- 用新的展示稿件操作，保留已成功的稿件作備用。

## 三到五分鐘流程

1. 開場：「這是使用 Python Flask 和 PostgreSQL 的投稿審查網站，有作者與編輯兩種角色。」
2. 作者新增稿件：「儲存後是編輯中，可以修改和刪除。」
3. 作者送出：「送出後變成審查中，作者不能修改或刪除。」
4. 切換編輯，查看全文，退回：「退回會讓稿件回到編輯中。」
5. 切回作者修改，再次送出。
6. 編輯閱讀後通過；切回作者展示已通過。
7. 切換作者二，展示無法看到作者一稿件。
8. 另建草稿刪除；在 pgAdmin 查詢稿件，展示資料實際存於 PostgreSQL。

## 程式如何運作

瀏覽器送出表單 → Flask 的 route 接收資料 → database.py 的 Store 執行參數化 SQL → PostgreSQL 儲存 → Flask 重新導向清單 → Jinja 產生 HTML。

- Python：程式語言。
- Flask：處理網址與表單，回傳網頁。
- HTML/CSS：畫面結構與樣式。
- PostgreSQL：永久儲存使用者與稿件。
- GET：開啟頁面；POST：送出會改變資料的操作。
- 外鍵：review_articles.author_id 指向 review_users.id。
- 交易：成功才提交，失敗回滾。
- 角色切換：透過選單及 Flask session 保存目前展示身分，尚未做密碼登入。

若被問是否所有程式都自己寫，依實際情況說明使用 AI 協助，並能解釋自己展示的流程；課程若有 AI 使用規定，依規定辦理。

## 繳交

GitHub Repository 最外層放 app.py、database.py、schema.sql、requirements.txt、README.md、start.bat、操作說明.md、demo準備.md、.gitignore，以及完整 templates 與 static 資料夾。最後提交 Repository 首頁網址。

若之前已上傳視窗版，這次需要更新 app.py、requirements.txt、README 等檔案，並新增 database.py、templates、static。確認 GitHub 上顯示的是 Flask 版本。
