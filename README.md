# Sojusan GameList

[![GameList CI](https://github.com/SojusanApps/game-list-backend/actions/workflows/game-list.yml/badge.svg)](https://github.com/SojusanApps/game-list-backend/actions/workflows/game-list.yml)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=SojusanApps_game-list-backend&metric=coverage)](https://sonarcloud.io/summary/new_code?id=SojusanApps_game-list-backend)
[![prek](https://img.shields.io/badge/prek-enabled-brightgreen)](https://github.com/j178/prek)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Black](https://img.shields.io/badge/code%20style-black-black)](https://github.com/psf/black)
[![SonarCloud](https://sonarcloud.io/images/project_badges/sonarcloud-white.svg)](https://sonarcloud.io/summary/new_code?id=SojusanApps_game-list-backend)

Application to manage game lists.

## Basic assumptions

* [Python](https://www.python.org/) >= 3.14
* [Django](https://www.djangoproject.com/) >= 6.0
* REST API based on the [Django REST Framework](https://www.django-rest-framework.org/)
* Line length 120
* Language: English
* Tests performed with [pytest](https://docs.pytest.org/)
* Full compatibility with [PEP8](https://peps.python.org/pep-0008/)
* Assumed coverage in tests > 90%
* Automatic tests for PostgreSQL in GitHub CI
* Package management with [uv](https://docs.astral.sh/uv)
* Command runner: [just](https://github.com/casey/just)

## Available commands

Run `just --list` to see all available recipes. Common ones:

| Command | Description |
| --- | --- |
| `just sync` | Sync all dependencies |
| `just run` | Start the development server |
| `just fresh_run` | First-time setup: migrate, create superuser, start server |
| `just check` | Run ruff and mypy |
| `just test` | Run all tests |
| `just coverage` | Generate HTML coverage report |
| `just app_db` | Start the app PostgreSQL container |
| `just test_db` | Start the test PostgreSQL container |
| `just translations` | Extract translation strings |
| `just finish_translations` | Compile translation messages |
| `just generate_openapi` | Generate OpenAPI schema as `openapi.json` |
| `just import_igdb_data` | Import data from IGDB |
| `just recalculate_stats` | Recalculate game and user stats |
| `just tui` | Launch the custom management TUI |

## Assumptions about the release preparation and deployment methodology

1. I keep 2 branches:
   * **master**: The master branch of the repository contains the fully functional production code.
   * **devel**: The branch for development contains the functional code with new features.
1. I use versioning following the [semver 2.0](https://semver.org/spec/v2.0.0.html)
1. The `master` and `devel` branches should contain stable and working code.
1. Workflow:
    * The developer is preparing a branch with new functionality or a correction, giving it a name as *[bugfix/feature/hotfix]/[description]*, e.g. *feature/new-document*
    * When the code is ready, the developer prepares PR (Pull Request) for the **devel** branch for new functionalities
    * If all functionalities work, the code is uploaded to the **master** branch

Tag Legend:

* **latest** - The latest production version.

## Deploy

1. Create the file `docker-compose.yaml` and upload it to the production server. (only the first time)
1. Log in via ssh to the production server and execute the following commands:

   ```shell
   docker compose -f docker-compose.yml pull
   docker compose -f docker-compose.yml up --detach --force-recreate --remove-orphans
   ```

## Local installation

1. Clone the repository from GitHub with the command:

   ```shell
   git clone https://github.com/SojusanApps/game-list-backend.git
   ```

1. Install all project dependencies:

   ```shell
   uv sync --all-extras
   ```

1. Install the `prek` hooks:

   ```shell
   uv run prek install --hook-type pre-commit --hook-type pre-push
   ```

   To disable checking of certain hooks, you can use the `SKIP` variable, e.g.:

   ```shell
   SKIP=check-version-and-changelog git push
   ```

1. Create a new PostgreSQL database in docker:

   ```shell
   docker run --name game-list-postgres \
      -p 5432:5432 \
      -e POSTGRES_DB=game_list \
      -e POSTGRES_USER=game_list \
      -e POSTGRES_PASSWORD=game_list \
      -v game-list-postgres-data:/var/lib/postgresql \
      -d postgres:18.4-alpine
   ```

1. Run database migrations:

   ```shell
   uv run scripts/game-list-manage.py migrate
   ```

1. Create a Django admin account:

   ```shell
   uv run scripts/game-list-manage.py createsuperuser
   ```

1.Start the development server:

   ```shell
   uv run scripts/game-list-manage.py runserver
   ```

## Configuration

* All configurations can be found in `game_list/settings/`
* **base.py** - contains the base configuration of the application
* **devel.py** - includes development configuration
* **test.py** - contains configuration for tests
* You can set up any configuration file using the `DJANGO_SETTINGS_MODULE` environment variable

## Swagger

Swagger enables you to visualize and interact with a RESTful API. It generates automatically based on the OpenAPI specification, a list of available endings along with the documentation contained in the code. In addition, it presents examples of data structures that should be sent to a given end and enables direct interaction with them.

Swagger is available at: [http://127.0.0.1:8000/api/schema/swagger-ui](http://127.0.0.1:8000/api/schema/swagger-ui)

## Tests

1. Running tests using the PostgreSQL database:

   ```shell
   uv run scripts/game-list-run-tests-with-pg.sh
   ```

2. Starting the full test stack with the tox utility:

   ```shell
   uv run tox
   ```
