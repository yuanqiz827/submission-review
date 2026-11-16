from pathlib import Path
import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent

class Store:
    """每個操作使用獨立交易；失敗時自動回滾。"""
    def __init__(self, config):
        self.config = dict(config)

    def connect(self):
        return psycopg.connect(**self.config, connect_timeout=5, row_factory=dict_row)

    def initialize(self):
        with self.connect() as conn:
            conn.execute((ROOT / 'schema.sql').read_text(encoding='utf-8'))

    def users(self):
        with self.connect() as conn:
            return conn.execute('SELECT * FROM review_users ORDER BY id').fetchall()

    def articles(self, user):
        with self.connect() as conn:
            query = '''SELECT a.*, u.display_name AS author_name
                       FROM review_articles a JOIN review_users u ON u.id = a.author_id'''
            if user['role'] == 'author':
                return conn.execute(query + ' WHERE a.author_id = %s ORDER BY a.id DESC',
                                    (user['id'],)).fetchall()
            return conn.execute(query + " WHERE a.status = 'reviewing' ORDER BY a.id").fetchall()

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

    def act(self, user, article_id, action):
        with self.connect() as conn:
            if action == 'delete' and user['role'] == 'author':
                result = conn.execute('''DELETE FROM review_articles WHERE id = %s
                    AND author_id = %s AND status = 'editing' RETURNING id''',
                    (article_id, user['id'])).fetchone()
            elif action == 'submit' and user['role'] == 'author':
                result = conn.execute('''UPDATE review_articles SET status = 'reviewing',
                    updated_at = CURRENT_TIMESTAMP WHERE id = %s AND author_id = %s
                    AND status = 'editing' RETURNING id''', (article_id, user['id'])).fetchone()
            elif action in ('approve', 'return') and user['role'] == 'editor':
                target = 'approved' if action == 'approve' else 'editing'
                result = conn.execute('''UPDATE review_articles SET status = %s,
                    updated_at = CURRENT_TIMESTAMP WHERE id = %s AND status = 'reviewing'
                    RETURNING id''', (target, article_id)).fetchone()
            else:
                raise ValueError('這個角色無法執行此操作。')
            if not result:
                raise ValueError('稿件狀態或作者不符，請重新整理清單。')


