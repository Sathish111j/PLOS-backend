FROM kong:latest

# Install required plugins
USER root

# Copy Kong configuration
COPY services/api-gateway/kong.conf /etc/kong/kong.conf

# Copy initialization script
COPY services/api-gateway/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

USER kong

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["kong", "docker-start"]
