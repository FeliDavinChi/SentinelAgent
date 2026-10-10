-- 1. Create the application user and database
-- Run as a superuser (e.g., postgres)
CREATE USER sentinel_app WITH PASSWORD '12345678';
CREATE DATABASE sentinelagent OWNER sentinel_app;

-- Connect to the sentinelagent database and run the following:
\c sentinelagent

-- 2. Create the Users table
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    role VARCHAR(50) NOT NULL,
    department VARCHAR(50) NOT NULL,
    clearance VARCHAR(50) NOT NULL
);

-- 3. Create the Documents table
CREATE TABLE documents (
    document_id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    department VARCHAR(50) NOT NULL,
    classification VARCHAR(50) NOT NULL,
    owner VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    effective_date DATE NOT NULL,
    content TEXT NOT NULL
);

-- 4. Create the Audit Logs table
CREATE TABLE audit_logs (
    request_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    question TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rows_returned INTEGER NOT NULL,
    rls_enforced BOOLEAN NOT NULL,
    verification_status VARCHAR(50) NOT NULL,
    final_status VARCHAR(50) NOT NULL
);

-- 5. Insert Mock Users (For diverse testing of RLS)
INSERT INTO users (user_id, role, department, clearance) VALUES
('U102', 'Finance Associate', 'Finance', 'Internal'),
('U301', 'Finance Manager', 'Finance', 'Confidential'),
('U505', 'Finance Executive', 'Finance', 'Restricted'),
('U205', 'Marketing Associate', 'Marketing', 'Internal');

-- 6. Helper Function for Clearance Hierarchy
-- Maps clearance strings to integer levels for comparison
CREATE OR REPLACE FUNCTION clearance_level(c VARCHAR) RETURNS INTEGER AS $$
BEGIN
    RETURN CASE c
        WHEN 'Internal' THEN 1
        WHEN 'Confidential' THEN 2
        WHEN 'Restricted' THEN 3
        ELSE 0
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 7. Enable Row-Level Security on Documents
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- 8. Define Strict Hierarchical RLS Policies
-- Policy: A user can see documents IF:
-- 1) The document belongs to their department
-- 2) The document's classification level is <= their clearance level

CREATE POLICY hierarchical_access_policy ON documents
FOR SELECT
TO sentinel_app
USING (
    department = (
        SELECT department FROM users 
        WHERE user_id = current_setting('app.user_id', true)
    )
    AND
    clearance_level(classification) <= clearance_level((
        SELECT clearance FROM users 
        WHERE user_id = current_setting('app.user_id', true)
    ))
);

-- Insert policy: User uploads inherit their own department and cannot exceed their clearance
CREATE POLICY hierarchical_insert_policy ON documents
FOR INSERT
TO sentinel_app
WITH CHECK (
    department = (
        SELECT department FROM users 
        WHERE user_id = current_setting('app.user_id', true)
    )
    AND
    clearance_level(classification) <= clearance_level((
        SELECT clearance FROM users 
        WHERE user_id = current_setting('app.user_id', true)
    ))
);

-- 9. Grant privileges to the application user
GRANT ALL PRIVILEGES ON TABLE documents TO sentinel_app;
GRANT ALL PRIVILEGES ON TABLE users TO sentinel_app;
GRANT ALL PRIVILEGES ON TABLE audit_logs TO sentinel_app;
GRANT USAGE, SELECT ON SEQUENCE audit_logs_request_id_seq TO sentinel_app;
