from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
DEMO_ACCOUNTS = {'author1': 'Author123!', 'author2': 'Author123!', 'editor1': 'Editor123!'}

class Store:
    """每個操作使用獨立交易；失敗時自動回滾。"""
    def __init__(self, config):
        self.config = dict(config)

    def connect(self):
        return psycopg.connect(**self.config, connect_timeout=5, row_factory=dict_row)

    def initialize(self):
        with self.connect() as conn:
            conn.execute((ROOT / 'schema.sql').read_text(encoding='utf-8'))
            for username, password in DEMO_ACCOUNTS.items():
                # Only initialize missing passwords; reconnecting never resets them.
                row = conn.execute('SELECT password_hash FROM review_users WHERE username = %s',
                                   (username,)).fetchone()
                if row and not row['password_hash']:
                    conn.execute('''UPDATE review_users SET password_hash = %s
                        WHERE username = %s AND (password_hash IS NULL OR password_hash = '')''',
                        (generate_password_hash(password), username))

    def users(self):
        with self.connect() as conn:
            return conn.execute('SELECT id, username, display_name, role FROM review_users ORDER BY id').fetchall()

    def user(self, user_id):
        with self.connect() as conn:
            return conn.execute('''SELECT id, username, display_name, role FROM review_users
                WHERE id = %s''', (user_id,)).fetchone()

    def authenticate(self, username, password):
        if not username or not password or len(username) > 40 or len(password) > 256:
            return None
        with self.connect() as conn:
            row = conn.execute('SELECT * FROM review_users WHERE username = %s', (username,)).fetchone()
        if not row or not row['password_hash']:
            return None
        if not check_password_hash(row['password_hash'], password):
            return None
        return {key: row[key] for key in ('id', 'username', 'display_name', 'role')}

    def articles(self, user):
        with self.connect() as conn:
            query = '''SELECT a.*, u.display_name AS author_name
                       FROM review_articles a JOIN review_users u ON u.id = a.author_id'''
            if user['role'] == 'author':
                return conn.execute(query + ' WHERE a.author_id = %s ORDER BY a.id DESC',
                                    (user['id'],)).fetchall()
            if user['role'] == 'editor':
                return conn.execute(query + " WHERE a.status = 'reviewing' ORDER BY a.id").fetchall()
            raise ValueError('無效的使用者角色。')

    def article(self, user, article_id):
        with self.connect() as conn:
            query = '''SELECT a.*, u.display_name AS author_name
                       FROM review_articles a JOIN review_users u ON u.id = a.author_id
                       WHERE a.id = %s'''
            if user['role'] == 'author':
                return conn.execute(query + ' AND a.author_id = %s', (article_id, user['id'])).fetchone()
            if user['role'] == 'editor':
                return conn.execute(query + " AND a.status = 'reviewing'", (article_id,)).fetchone()
            return None

    def save(self, user, category, title, content, article_id=None):
        if user['role'] != 'author':
            raise ValueError('只有作者可以儲存稿件。')
        category, title, content = category.strip(), title.strip(), content.strip()
        if not all((category, title, content)):
            raise ValueError('類別、標題和文章內容都必須填寫。')
        if len(category) > 40 or len(title) > 200:
            raise ValueError('類別最多 40 字，標題最多 200 字。')
        with self.connect() as conn:
            if article_id is None:
                return conn.execute('''INSERT INTO review_articles
                    (author_id, category, title, content) VALUES (%s, %s, %s, %s)
                    RETURNING id''', (user['id'], category, title, content)).fetchone()['id']
            result = conn.execute('''UPDATE review_articles SET category = %s, title = %s,
                content = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND author_id = %s AND status = 'editing' RETURNING id''',
                (category, title, content, article_id, user['id'])).fetchone()
            if not result:
                raise ValueError('只能修改自己「編輯中」的稿件，請重新整理清單。')
            return result['id']

    def act(self, user, article_id, action, feedback=''):
        if action == 'return' and user['role'] == 'editor':
            feedback = feedback.strip()
            if not feedback:
                raise ValueError('退回稿件前，請填寫意見回饋。')
            if len(feedback) > 2000:
                raise ValueError('意見回饋最多 2000 字。')
        with self.connect() as conn:
            if action == 'delete' and user['role'] == 'author':
                result = conn.execute('''DELETE FROM review_articles WHERE id = %s
                    AND author_id = %s AND status = 'editing' RETURNING id''',
                    (article_id, user['id'])).fetchone()
            elif action == 'submit' and user['role'] == 'author':
                result = conn.execute('''UPDATE review_articles SET status = 'reviewing',
                    updated_at = CURRENT_TIMESTAMP WHERE id = %s AND author_id = %s
                    AND status = 'editing' RETURNING id''', (article_id, user['id'])).fetchone()
            elif action == 'return' and user['role'] == 'editor':
                result = conn.execute('''UPDATE review_articles SET status = 'editing',
                    review_feedback = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND status = 'reviewing' RETURNING id''',
                    (feedback, article_id)).fetchone()
            elif action == 'approve' and user['role'] == 'editor':
                result = conn.execute('''UPDATE review_articles SET status = 'approved',
                    updated_at = CURRENT_TIMESTAMP WHERE id = %s AND status = 'reviewing'
                    RETURNING id''', (article_id,)).fetchone()
            else:
                raise ValueError('這個角色無法執行此操作。')
            if not result:
                raise ValueError('稿件狀態或作者不符，請重新整理清單。')


