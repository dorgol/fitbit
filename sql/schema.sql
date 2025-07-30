-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    age INTEGER,
    gender VARCHAR(10),
    location VARCHAR(100),
    goals JSONB,
    preferences JSONB
);

-- Health metrics table
CREATE TABLE health_metrics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    metric_type VARCHAR(50),
    value FLOAT,
    timestamp TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_health_metrics_user_time ON health_metrics(user_id, timestamp DESC);
