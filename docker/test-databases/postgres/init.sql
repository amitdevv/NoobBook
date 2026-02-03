-- Seed schema/data for the dummy Postgres database used in NoobBook testing.

CREATE TABLE IF NOT EXISTS customers (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
  id SERIAL PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  amount_cents INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO customers (email, name, created_at) VALUES
  ('alice@example.com', 'Alice', NOW() - INTERVAL '40 days'),
  ('bob@example.com', 'Bob', NOW() - INTERVAL '25 days'),
  ('carol@example.com', 'Carol', NOW() - INTERVAL '10 days'),
  ('dave@example.com', 'Dave', NOW() - INTERVAL '5 days'),
  ('erin@example.com', 'Erin', NOW() - INTERVAL '1 day')
ON CONFLICT (email) DO NOTHING;

-- Some orders across statuses and dates
INSERT INTO orders (customer_id, amount_cents, status, created_at)
SELECT c.id, o.amount_cents, o.status, o.created_at
FROM (
  VALUES
    ('alice@example.com', 1299, 'paid', NOW() - INTERVAL '35 days'),
    ('alice@example.com', 2599, 'refunded', NOW() - INTERVAL '20 days'),
    ('bob@example.com', 9900, 'paid', NOW() - INTERVAL '14 days'),
    ('bob@example.com', 4999, 'paid', NOW() - INTERVAL '7 days'),
    ('carol@example.com', 1999, 'pending', NOW() - INTERVAL '3 days'),
    ('dave@example.com', 8999, 'paid', NOW() - INTERVAL '2 days'),
    ('erin@example.com', 1499, 'paid', NOW() - INTERVAL '1 day')
) AS o(email, amount_cents, status, created_at)
JOIN customers c ON c.email = o.email
ON CONFLICT DO NOTHING;

