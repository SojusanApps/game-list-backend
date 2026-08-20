# Show the list of available commands
help:
    just --list

# Sync all dependencies
sync:
    uv sync --all-extras

# Start the application on the default port
run:
    uv run scripts/my-game-list-manage.py runserver

# First start: collect static files, run migrations, create superuser, start server
fresh_run:
    uv run scripts/my-game-list-manage.py collectstatic
    uv run scripts/my-game-list-manage.py makemigrations
    uv run scripts/my-game-list-manage.py migrate
    uv run scripts/my-game-list-manage.py createsuperuser
    uv run scripts/my-game-list-manage.py runserver

# Check code correctness with ruff and mypy
check:
    uv run ruff check .
    uv run mypy . --strict

# Prepare translations for supported languages
translations:
    uv run scripts/my-game-list-manage.py makemessages -l pl

# Compile translation messages
finish_translations:
    uv run scripts/my-game-list-manage.py compilemessages

# Prepare the coverage report in HTML format
coverage:
    uv run coverage html

# Generate OpenAPI schema in JSON format
generate_openapi:
    uv run scripts/my-game-list-manage.py spectacular --format openapi-json --file openapi.json

# Run a Docker container with the app database
app_db:
    docker run --name dev-my-game-list-postgres \
        -p 5432:5432 \
        -e POSTGRES_DB=my_game_list \
        -e POSTGRES_USER=my_game_list \
        -e POSTGRES_PASSWORD=my_game_list \
        -v dev-my-game-list-postgres-data:/var/lib/postgresql \
        -d postgres:18.4-alpine

# Run a Docker container with the test database
test_db:
    docker run --name pytest_postgresql \
        -e POSTGRES_USER=pytest_postgresql \
        -e POSTGRES_PASSWORD=pytest_postgresql \
        -e POSTGRES_DB=pytest_postgresql \
        -p 127.0.0.1:9999:5432 \
        -d postgres:18.4-alpine

# Run all tests for the application
test:
    uv run pytest -n auto

# Run the custom TUI for managing the application
tui:
    uv run scripts/my-game-list-manage.py custom_tui

# Import data from IGDB to the application database
import_igdb_data:
    uv run scripts/my-game-list-manage.py import_data_from_igdb platforms genres game_modes player_perspectives \
        game_engines game_types game_statuses external_game_sources external_games companies games

# Recalculate all stats for games and users (run after importing IGDB data)
recalculate_stats:
    uv run scripts/my-game-list-manage.py recalculate_stats
