FROM kong:2.8.1

COPY volumes/api/kong.yml /home/kong/temp.yml
