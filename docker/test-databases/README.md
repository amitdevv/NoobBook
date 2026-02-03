# Test databases (Postgres + MySQL)

These are **dummy** databases you can run locally to test NoobBook’s DATABASE sources and `analyze_database_agent` tool.

## Start

```bash
docker compose -f docker/test-databases/docker-compose.yml up -d
```

## Connection URIs

### From the host machine (e.g. when running backend locally)

- Postgres: `postgresql://test_user:test_password@localhost:5433/test_postgres_db`
- MySQL: `mysql://test_user:test_password@localhost:3307/test_mysql_db`

### From the NoobBook backend container (same `noobbook-network`)

- Postgres: `postgresql://test_user:test_password@noobbook-test-postgres:5432/test_postgres_db`
- MySQL: `mysql://test_user:test_password@noobbook-test-mysql:3306/test_mysql_db`

## Stop

```bash
docker compose -f docker/test-databases/docker-compose.yml down
```

