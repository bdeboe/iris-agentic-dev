# The task image for one arm of the iris-agentic-dev benchmark.
#
# The iad binary is copied out of the published release image at a pinned tag. The tools are
# what this benchmark measures, so the environment must not resolve a newer surface than the
# run it is part of. A floating tag is not allowed here, ever.
FROM ghcr.io/intersystems-community/iris-agentic-dev:v1.4.2 AS iad

FROM ubuntu:24.04
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=iad /iris-agentic-dev /usr/local/bin/iris-agentic-dev
COPY seed.sh /usr/local/bin/seed.sh
RUN chmod +x /usr/local/bin/iris-agentic-dev /usr/local/bin/seed.sh
WORKDIR /workspace
