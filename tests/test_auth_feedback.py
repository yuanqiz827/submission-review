"""Run: python -m unittest discover -s tests -v

HTTP and permission tests use an in-memory Store double. PostgreSQL connection
and migration are checked separately against a configured database.
"""
import unittest
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from app import create_app
from database import Store


class MemoryStore:
    def __init__(self):
        self.people = [
            dict(id=1, username='author1', display_name='作者一', role='author'),
            dict(id=2, username='author2', display_name='作者二', role='author'),
            dict(id=3, username='editor1', display_name='編輯', role='editor')]
        self.records = {7: dict(id=7, author_id=1, author_name='作者一', category='校園生活',
            title='測試稿件', content='原始內容', status='reviewing', review_feedback='')}

    def user(self, user_id):
        return next((dict(u) for u in self.people if u['id'] == user_id), None)

    def authenticate(self, username, password):
        if password != 'test-password':
            return None
        return next((dict(u) for u in self.people if u['username'] == username), None)

    def articles(self, user):
        return [dict(a) for a in self.records.values() if
                (a['author_id'] == user['id'] if user['role'] == 'author' else a['status'] == 'reviewing')]

    def article(self, user, article_id):
        return next((a for a in self.articles(user) if a['id'] == article_id), None)

    def save(self, user, category, title, content, article_id=None):
        if article_id is not None:
            self.records[article_id].update(category=category, title=title, content=content)
        return article_id or 8

    def act(self, user, article_id, action, feedback=''):
        article = self.records[article_id]
        if user['role'] == 'editor' and article['status'] == 'reviewing':
            if action == 'return':
                if not feedback.strip():
                    raise ValueError('退回稿件前，請填寫意見回饋。')
                if len(feedback.strip()) > 2000:
                    raise ValueError('意見回饋最多 2000 字。')
                article.update(status='editing', review_feedback=feedback.strip())
                return
            if action == 'approve':
                article['status'] = 'approved'
                return
        if user['role'] == 'author' and user['id'] == article['author_id'] and article['status'] == 'editing':
            if action == 'submit':
                article['status'] = 'reviewing'
                return
        raise ValueError('這個角色無法執行此操作。')


class AuthFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.app = create_app(self.store)
        self.app.testing = True
        self.client = self.app.test_client()
        self.client.get('/login')

    def post(self, path, **data):
        with self.client.session_transaction() as session:
            csrf = session['csrf_token']
        return self.client.post(path, data=dict(data, csrf_token=csrf))

    def login(self, username='author1'):
        response = self.post('/login', username=username, password='test-password')
        self.assertEqual(response.status_code, 302)
        self.client.get('/')

    def test_login_required_and_no_default_author(self):
        for path in ('/', '/articles/new', '/articles/7'):
            self.assertTrue(self.client.get(path).location.endswith('/login'))
        self.assertTrue(self.post('/articles/7/approve').location.endswith('/login'))

    def test_wrong_password_and_csrf(self):
        response = self.post('/login', username='editor1', password='wrong')
        self.assertEqual(response.status_code, 401)
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)
        self.assertEqual(self.client.post('/login', data={'username': 'editor1'}).status_code, 400)

    def test_login_ignores_spoofed_role_and_identity_endpoint_removed(self):
        self.post('/login', username='author1', password='test-password', role='editor', user_id='3')
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.assertEqual(session['user_id'], 1)
            self.assertNotIn('password', session)
            self.assertNotIn('role', session)
        self.assertEqual(self.post('/identity', user_id='3').status_code, 404)
        self.assertEqual(self.client.get('/setup').status_code, 403)
        self.post('/articles/7/approve')
        self.assertEqual(self.store.records[7]['status'], 'reviewing')

    def test_logout_and_distinct_browser_sessions(self):
        self.login()
        other = self.app.test_client()
        self.assertTrue(other.get('/').location.endswith('/login'))
        self.post('/logout')
        self.assertTrue(self.client.get('/').location.endswith('/login'))

    def test_author_cannot_read_other_author_or_edit_reviewing(self):
        self.login('author2')
        self.assertEqual(self.client.get('/articles/7').status_code, 404)
        self.assertNotIn('測試稿件', self.client.get('/').get_data(as_text=True))
        self.post('/logout')
        self.client.get('/login')
        self.login('author1')
        self.assertEqual(self.post('/articles/7', title='forged', content='forged').status_code, 403)

    def test_editor_cannot_create(self):
        self.login('editor1')
        self.assertEqual(self.client.get('/articles/new').status_code, 403)

    def test_empty_feedback_keeps_reviewing_and_long_feedback_is_retained(self):
        self.login('editor1')
        for feedback in ('   ', '字' * 2001):
            response = self.post('/articles/7/return', feedback=feedback)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.store.records[7]['status'], 'reviewing')
        self.assertIn('字' * 2001, response.get_data(as_text=True))

    def test_feedback_workflow_and_html_escaping(self):
        self.login('editor1')
        feedback = '請補充具體例子。\n<script>alert(1)</script>'
        self.assertEqual(self.post('/articles/7/return', feedback=feedback).status_code, 302)
        self.assertEqual(self.store.records[7]['status'], 'editing')
        self.post('/logout')
        self.client.get('/login')
        self.login('author1')
        page = self.client.get('/articles/7').get_data(as_text=True)
        self.assertIn('請補充具體例子。', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<script>alert(1)</script>', page)
        self.post('/articles/7', category='校園生活', title='修訂稿件', content='補充例子')
        self.post('/articles/7/submit')
        self.post('/logout')
        self.client.get('/login')
        self.login('editor1')
        self.post('/articles/7/approve')
        self.assertEqual(self.store.records[7]['status'], 'approved')
        self.assertEqual(self.store.records[7]['review_feedback'], feedback)

    def test_reconnect_invalidates_old_sessions(self):
        self.login()
        self.app.config['AUTH_VERSION'] = 'a-new-database'
        self.assertTrue(self.client.get('/').location.endswith('/login'))


class DatabaseRuleTests(unittest.TestCase):
    def setUp(self):
        self.store = Store({})
        self.conn = MagicMock()
        self.store.connect = MagicMock()
        self.store.connect.return_value.__enter__.return_value = self.conn
        self.author = dict(id=1, role='author')
        self.editor = dict(id=3, role='editor')

    def test_hashed_password_verification(self):
        self.conn.execute.return_value.fetchone.return_value = dict(
            id=1, username='author1', display_name='作者一', role='author',
            password_hash=generate_password_hash('test-password'))
        self.assertEqual(self.store.authenticate('author1', 'test-password')['role'], 'author')
        self.assertIsNone(self.store.authenticate('author1', 'wrong'))
        self.assertNotIn('password_hash', self.store.authenticate('author1', 'test-password'))

    def test_feedback_is_required_before_connecting(self):
        for text in ('', '  ', '字' * 2001):
            with self.assertRaises(ValueError):
                self.store.act(self.editor, 7, 'return', text)
        self.store.connect.assert_not_called()

    def test_return_updates_status_and_feedback_atomically(self):
        self.conn.execute.return_value.fetchone.return_value = dict(id=7)
        feedback = "請補充來源；' 不應當成 SQL"
        self.store.act(self.editor, 7, 'return', feedback)
        query, parameters = self.conn.execute.call_args.args
        self.assertIn("status = 'editing'", query)
        self.assertIn("status = 'reviewing'", query)
        self.assertIn('review_feedback = %s', query)
        self.assertNotIn(feedback, query)
        self.assertEqual(parameters, (feedback, 7))

    def test_author_cannot_review_and_stale_return_fails(self):
        with self.assertRaises(ValueError):
            self.store.act(self.author, 7, 'return', 'fake')
        self.conn.execute.assert_not_called()
        self.conn.execute.return_value.fetchone.return_value = None
        with self.assertRaises(ValueError):
            self.store.act(self.editor, 7, 'return', 'feedback')

    def test_reconnect_never_resets_initialized_passwords(self):
        self.conn.execute.return_value.fetchone.return_value = {'password_hash': 'already-set'}
        with patch('database.generate_password_hash') as hash_password:
            self.store.initialize()
        hash_password.assert_not_called()


if __name__ == '__main__':
    unittest.main()
