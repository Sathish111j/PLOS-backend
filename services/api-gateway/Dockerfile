FROM kong:latest

# DB-less mode - no PostgreSQL client needed
USER root

# Copy Kong configuration
COPY services/api-gateway/kong.conf /etc/kong/kong.conf
COPY services/api-gateway/kong.yml /etc/kong/kong.yml

USER kong

# Start Kong directly (no migrations needed in DB-less mode)
CMD ["kong", "docker-start"]
