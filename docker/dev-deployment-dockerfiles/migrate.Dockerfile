FROM alpine:3.19

# Copy migration files into the image
COPY backend/supabase/init.sql /staging/init.sql
COPY backend/supabase/migrations/ /staging/migrations/

# On run, copy files to the shared volume mount point
CMD ["sh", "-c", "cp /staging/init.sql /init-files/ && cp -r /staging/migrations /init-files/ && echo 'Migration files staged.'"]
