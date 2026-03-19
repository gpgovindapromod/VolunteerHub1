-- Volunteer Hub Schema v2

DROP TABLE IF EXISTS certificates;
DROP TABLE IF EXISTS attendance_log;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS applications;
DROP TABLE IF EXISTS activity_roles;
DROP TABLE IF EXISTS activity_days;
DROP TABLE IF EXISTS activities;
DROP TABLE IF EXISTS volunteers;
DROP TABLE IF EXISTS organizations;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT UNIQUE NOT NULL,
    password   TEXT NOT NULL,
    role       TEXT NOT NULL CHECK(role IN ('volunteer','organization','admin')),
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE volunteers (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    phone    TEXT,
    bio      TEXT,
    skills   TEXT,
    college  TEXT,
    year     TEXT
);

CREATE TABLE organizations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_type    TEXT,
    description TEXT,
    website     TEXT
);

CREATE TABLE activities (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id       INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    description  TEXT,
    start_date   DATE,
    end_date     DATE,
    time         TEXT,
    location     TEXT,
    deadline     DATE,
    requirements TEXT,
    status       TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed','draft')),
    auto_assign  INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stores each day of a multi-day activity
CREATE TABLE activity_days (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    day_date    DATE NOT NULL,
    label       TEXT
);

CREATE TABLE activity_roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    total       INTEGER NOT NULL DEFAULT 1,
    filled      INTEGER NOT NULL DEFAULT 0,
    skill_tags  TEXT   -- comma-separated required skills (optional)
);

CREATE TABLE applications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id) ON DELETE CASCADE,
    activity_id  INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    role_applied TEXT NOT NULL,
    motivation   TEXT,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(volunteer_id, activity_id)
);

CREATE TABLE assignments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id) ON DELETE CASCADE,
    activity_id  INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    role         TEXT NOT NULL,
    assigned_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-day attendance
CREATE TABLE attendance_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    day_id        INTEGER REFERENCES activity_days(id) ON DELETE CASCADE,
    day_date      DATE NOT NULL,
    is_present    INTEGER NOT NULL DEFAULT 0,
    marked_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(assignment_id, day_date)
);

CREATE TABLE certificates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id) ON DELETE CASCADE,
    activity_id  INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    issued_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    issued_by    INTEGER REFERENCES users(id),
    UNIQUE(volunteer_id, activity_id)
);
ALTER TABLE volunteers ADD COLUMN photo BLOB;
ALTER TABLE volunteers ADD COLUMN photo_mime TEXT;