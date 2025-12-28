FROM kong:3.4-alpine

# Install required plugins
USER root

# Copy Kong configuration
COPY kong.conf /etc/kong/kong.conf

# Copy initialization script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

USER kong

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["kong", "docker-start"]
