FROM supabase/postgres:15.8.1.085

# Bake init scripts into the image (bind mounts don't work in Coolify)
COPY volumes/db/realtime.sql  /docker-entrypoint-initdb.d/migrations/99-realtime.sql
COPY volumes/db/_supabase.sql /docker-entrypoint-initdb.d/migrations/97-_supabase.sql
COPY volumes/db/logs.sql      /docker-entrypoint-initdb.d/migrations/99-logs.sql
COPY volumes/db/pooler.sql    /docker-entrypoint-initdb.d/migrations/99-pooler.sql
COPY volumes/db/webhooks.sql  /docker-entrypoint-initdb.d/init-scripts/98-webhooks.sql
COPY volumes/db/roles.sql     /docker-entrypoint-initdb.d/init-scripts/99-roles.sql
COPY volumes/db/jwt.sql       /docker-entrypoint-initdb.d/init-scripts/99-jwt.sql
