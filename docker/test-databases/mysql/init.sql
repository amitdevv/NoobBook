-- Seed schema/data for the dummy MySQL database used in NoobBook testing.

CREATE TABLE IF NOT EXISTS customers (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  amount_cents INT NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(id)
) ENGINE=InnoDB;

INSERT IGNORE INTO customers (email, name, created_at) VALUES
  ('alice@example.com', 'Alice', NOW() - INTERVAL 40 DAY),
  ('bob@example.com', 'Bob', NOW() - INTERVAL 25 DAY),
  ('carol@example.com', 'Carol', NOW() - INTERVAL 10 DAY),
  ('dave@example.com', 'Dave', NOW() - INTERVAL 5 DAY),
  ('erin@example.com', 'Erin', NOW() - INTERVAL 1 DAY);

-- Some orders across statuses and dates
INSERT INTO orders (customer_id, amount_cents, status, created_at)
SELECT c.id, o.amount_cents, o.status, o.created_at
FROM (
  SELECT 'alice@example.com' AS email, 1299 AS amount_cents, 'paid' AS status, NOW() - INTERVAL 35 DAY AS created_at
  UNION ALL SELECT 'alice@example.com', 2599, 'refunded', NOW() - INTERVAL 20 DAY
  UNION ALL SELECT 'bob@example.com', 9900, 'paid', NOW() - INTERVAL 14 DAY
  UNION ALL SELECT 'bob@example.com', 4999, 'paid', NOW() - INTERVAL 7 DAY
  UNION ALL SELECT 'carol@example.com', 1999, 'pending', NOW() - INTERVAL 3 DAY
  UNION ALL SELECT 'dave@example.com', 8999, 'paid', NOW() - INTERVAL 2 DAY
  UNION ALL SELECT 'erin@example.com', 1499, 'paid', NOW() - INTERVAL 1 DAY
) o
JOIN customers c ON c.email = o.email;

