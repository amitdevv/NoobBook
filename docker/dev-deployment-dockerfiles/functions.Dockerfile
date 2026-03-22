FROM supabase/edge-runtime:v1.70.0

COPY docker/supabase/volumes/functions/ /home/deno/functions/
