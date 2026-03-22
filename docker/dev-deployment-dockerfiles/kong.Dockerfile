FROM kong:2.8.1

COPY docker/supabase/volumes/api/kong.yml /home/kong/temp.yml
