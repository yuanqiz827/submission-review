-- Run inside the submission_review database. The application also runs this file.
CREATE TABLE IF NOT EXISTS review_users (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(40) UNIQUE NOT NULL,
    display_name VARCHAR(80) NOT NULL,
    role VARCHAR(10) NOT NULL CHECK (role IN ('author', 'editor')),
    password_hash TEXT
);

CREATE TABLE IF NOT EXISTS review_articles (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES review_users(id),
    category VARCHAR(40) NOT NULL CHECK (length(trim(category)) > 0),
    title VARCHAR(200) NOT NULL CHECK (length(trim(title)) > 0),
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    status VARCHAR(10) NOT NULL DEFAULT 'editing'
        CHECK (status IN ('editing', 'reviewing', 'approved')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    review_feedback TEXT NOT NULL DEFAULT ''
);

-- Upgrade existing installations without deleting users or articles.
ALTER TABLE review_users ADD COLUMN IF NOT EXISTS password_hash TEXT;
ALTER TABLE review_articles ADD COLUMN IF NOT EXISTS review_feedback TEXT NOT NULL DEFAULT '';

INSERT INTO review_users (username, display_name, role) VALUES
    ('author1', '作者一', 'author'),
    ('author2', '作者二', 'author'),
    ('editor1', '編輯', 'editor')
ON CONFLICT (username) DO NOTHING;
