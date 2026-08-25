FROM python:3.14.2-slim
# Copy uv and uvx from the uv image
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

# Define ARG with a default value
ARG MGL_LOG_DIR_PATH=/var/log/game_list/
# Optionally set ENV for runtime
ENV MGL_LOG_DIR_PATH=${MGL_LOG_DIR_PATH}

# Create a new non-root user
RUN adduser --system --no-create-home nonroot

# To locally connect your container image to a repository:
LABEL org.opencontainers.image.source=https://github.com/SojusanApps/game-list-backend

# App directory
WORKDIR /var/www/game-list

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy
# Ensure installed tools can be executed out of the box
ENV UV_TOOL_BIN_DIR=/usr/local/bin

# Remove the `git` installation once the packages for `django-prometheus` and `django-celery-beat` are updated to support newer Django
RUN apt-get update \
    && apt-get -y install --no-install-recommends curl=8.14.1-2+deb13u4 \
    && apt-get -y install --no-install-recommends git=1:2.47.3-0+deb13u1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY settings.py gunicorn.conf.py entrypoint.sh *.whl ./

# Installing separately from its dependencies allows optimal layer caching
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-cache-dir -U ./*.whl

# Place executables in the environment at the front of the path
ENV PATH="/.venv/bin:$PATH"

# Create the needed directories and set a non-root user as the owner to omit the permission error
RUN mkdir -p "${MGL_LOG_DIR_PATH}" && chown -R nonroot: "${MGL_LOG_DIR_PATH}" && \
    mkdir -p /opt/game_list/static && chown -R nonroot: /opt/game_list/static && \
    mkdir -p /home/nonroot/.cache && chown -R nonroot: /home/nonroot/.cache && \
    mkdir -p /home/nonroot/.gunicorn && chown -R nonroot: /home/nonroot/.gunicorn

ENV HOME=/home/nonroot
# Run application as non-root user
USER nonroot

ENTRYPOINT ["./entrypoint.sh"]
