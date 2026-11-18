"""投稿審查系統：Flask + PostgreSQL，執行 python app.py。"""
import os
import secrets
from functools import wraps

import psycopg
from psycopg import sql
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from database import Store

STATUS = {'editing': '編輯中', 'reviewing': '審查中', 'approved': '已通過'}


def create_app(store=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_hex(32), STORE=store, AUTH_VERSION=secrets.token_hex(16),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
    )

    def current_user():
        return getattr(g, 'user', None)

    @app.context_processor
    def shared():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_urlsafe(32)
        return dict(status_labels=STATUS, csrf_token=session['csrf_token'], current_user=current_user())

    @app.before_request
    def check_form_token():
        g.user = None
        if (app.config['STORE'] is not None and session.get('user_id') is not None
                and session.get('auth_version') == app.config['AUTH_VERSION']):
            g.user = app.config['STORE'].user(session['user_id'])
        if request.method == 'POST':
            expected = session.get('csrf_token', '')
            supplied = request.form.get('csrf_token', '')
            if not expected or not secrets.compare_digest(expected, supplied):
                return render_template('error.html', message='表單已過期，請重新整理頁面後再操作。'), 400

    def connected(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if app.config['STORE'] is None:
                return redirect(url_for('setup'))
            if current_user() is None:
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapper

    @app.errorhandler(psycopg.Error)
    def database_error(error):
        app.logger.error('PostgreSQL operation failed: %s', type(error).__name__)
        return render_template('error.html', message='無法完成資料庫操作。請確認 PostgreSQL 服務仍在執行，或回連線設定重新連線。'), 503

    @app.errorhandler(404)
    def not_found(error):
        return render_template('error.html', message='找不到這篇稿件，或目前身分無法查看。'), 404

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('error.html', message='目前帳號沒有執行這個操作的權限。'), 403

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if app.config['STORE'] is None:
            return redirect(url_for('setup'))
        if current_user() is not None:
            return redirect(url_for('index'))
        username = request.form.get('username', '').strip() if request.method == 'POST' else ''
        error = None
        if request.method == 'POST':
            user = app.config['STORE'].authenticate(username, request.form.get('password', ''))
            if user is not None:
                session.clear()
                session['user_id'] = user['id']
                session['auth_version'] = app.config['AUTH_VERSION']
                flash(f"{user['display_name']}，登入成功。", 'success')
                return redirect(url_for('index'))
            error = '帳號或密碼不正確，請重新輸入。'
        return render_template('login.html', username=username, error=error), 401 if error else 200

    @app.post('/logout')
    @connected
    def logout():
        session.clear()
        flash('已登出。切換角色請使用另一組帳號登入。', 'success')
        return redirect(url_for('login'))

    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        if app.config['STORE'] is not None:
            if current_user() is None:
                return redirect(url_for('login'))
            if current_user()['role'] != 'editor':
                abort(403)
        values = dict(host='localhost', port='5432', dbname='submission_review', user='postgres')
        error = None
        if request.method == 'POST':
            values.update({key: request.form.get(key, '').strip() for key in values})
            try:
                config = dict(values, password=request.form.get('password', ''))
                config['port'] = int(config['port'])
                if not all(config[key] for key in ('host', 'dbname', 'user')):
                    raise ValueError('伺服器、資料庫名稱與帳號都必須填寫。')
                if request.form.get('mode') == 'create':
                    with psycopg.connect(**dict(config, dbname='postgres'), connect_timeout=5,
                                         autocommit=True) as conn:
                        exists = conn.execute('SELECT 1 FROM pg_database WHERE datname = %s',
                                              (config['dbname'],)).fetchone()
                        if not exists:
                            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(config['dbname'])))
                candidate = Store(config)
                candidate.initialize()
                users = candidate.users()
                if not users:
                    raise ValueError('找不到可用的展示身分。')
                app.config['STORE'] = candidate
                app.config['AUTH_VERSION'] = secrets.token_hex(16)
                session.clear()
                flash('PostgreSQL 已連線，請使用作者或編輯帳號登入。', 'success')
                return redirect(url_for('login'))
            except (psycopg.Error, ValueError) as exc:
                error = str(exc)
        return render_template('setup.html', values=values, error=error)

    @app.get('/')
    @connected
    def index():
        user = current_user()
        if user is None:
            return redirect(url_for('setup'))
        store = app.config['STORE']
        return render_template('index.html', user=user, articles=store.articles(user))

    @app.route('/articles/new', methods=['GET', 'POST'])
    @connected
    def new_article():
        user = current_user()
        if user is None or user['role'] != 'author':
            abort(403)
        article = dict(category='校園生活', title='', content='', status='editing',
                       author_name=user['display_name'], review_feedback='')
        if request.method == 'POST':
            article.update({key: request.form.get(key, '') for key in ('category', 'title', 'content')})
            try:
                app.config['STORE'].save(user, article['category'], article['title'], article['content'])
                flash('稿件已儲存，狀態為「編輯中」。', 'success')
                return redirect(url_for('index'))
            except ValueError as exc:
                flash(str(exc), 'error')
        return render_template('article.html', user=user, article=article, editable=True, new=True)

    @app.route('/articles/<int:article_id>', methods=['GET', 'POST'])
    @connected
    def article_detail(article_id):
        user = current_user()
        if user is None:
            return redirect(url_for('setup'))
        store = app.config['STORE']
        article = store.article(user, article_id)
        if article is None:
            abort(404)
        editable = user['role'] == 'author' and article['status'] == 'editing'
        if request.method == 'POST':
            if not editable:
                abort(403)
            article.update({key: request.form.get(key, '') for key in ('category', 'title', 'content')})
            try:
                store.save(user, article['category'], article['title'], article['content'], article_id)
                flash('修改已儲存。', 'success')
                return redirect(url_for('index'))
            except ValueError as exc:
                flash(str(exc), 'error')
        return render_template('article.html', user=user, article=article, editable=editable, new=False)

    @app.post('/articles/<int:article_id>/<action>')
    @connected
    def article_action(article_id, action):
        if action not in ('delete', 'submit', 'approve', 'return'):
            abort(404)
        user = current_user()
        if user is None:
            return redirect(url_for('setup'))
        try:
            app.config['STORE'].act(user, article_id, action, request.form.get('feedback', ''))
            label = {'delete': '稿件已刪除。', 'submit': '投稿已送出，等待編輯審查。',
                     'approve': '稿件已通過。', 'return': '稿件已退回，作者可以修改後重新送出。'}[action]
            flash(label, 'success')
        except ValueError as exc:
            flash(str(exc), 'error')
            if action == 'return' and user['role'] == 'editor':
                article = app.config['STORE'].article(user, article_id)
                if article is not None:
                    return render_template('article.html', user=user, article=article,
                        editable=False, new=False, feedback_draft=request.form.get('feedback', '')), 400
        return redirect(url_for('index'))

    return app


app = create_app()

if __name__ == '__main__':
    print('\n投稿審查系統：請在瀏覽器開啟 http://localhost:5000\n關閉網站伺服器：按 Ctrl+C\n')
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', '5000')), debug=False)
