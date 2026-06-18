-- Seed data: one user, one job, one question

INSERT INTO users (email, password_hash, name)
VALUES ('alice@example.com', 'fakehash', 'Alice')
ON CONFLICT DO NOTHING;

INSERT INTO jobs (title, description)
VALUES ('Java 后端开发工程师', '负责后端开发、微服务与高并发处理')
ON CONFLICT DO NOTHING;

INSERT INTO questions (title, body, type, difficulty)
VALUES ('HashMap 原理', '请解释 Java HashMap 的底层实现与扩容机制。', 'technical', 3)
ON CONFLICT DO NOTHING;

