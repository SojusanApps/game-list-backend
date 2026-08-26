#!/usr/bin/env python
# ruff: noqa: S603, S607
"""This module contains features for building and pushing docker images."""

import shutil
import subprocess
import sys
from itertools import chain
from pathlib import Path

import typer
from python_colors import print_error, print_info, print_warning

DOCKER_REGISTRY = "ghcr.io"
DOCKER_REGISTRY_PATH_APP = f"{DOCKER_REGISTRY}/sojusanapps/game-list-backend/app"
DOCKER_REGISTRY_PATH_NGINX = f"{DOCKER_REGISTRY}/sojusanapps/game-list-backend/nginx"
FAILURE_CODE = 1

app = typer.Typer()


@app.command()
def setup_project(path: str = typer.Option("dist", help="Path where .whl will be distributed.")) -> None:
    """Create whl file for the project."""
    print_info("Whl file creation - started.")

    build_response = subprocess.Popen(["uv", "build", "--wheel", "--out-dir", str(path)]).wait()

    if build_response != 0:
        print_error("Something went wrong while building!")
        sys.exit(FAILURE_CODE)

    print_info("Whl file creation - finished.")


@app.command()
def clean_up(
    dist_path: str = typer.Option(
        "dist",
        help="A path where .whl was distributed. A value set to None or 'None' prevents to remove dist directory.",
    ),
) -> None:
    """Cleaning after build project."""
    print_info("Cleaning after build project - started.")

    build_dir = ("build/",)
    egg_info_dir = Path().glob("*.egg-info/")
    dist_dir = () if not dist_path or dist_path == "None" else (dist_path,)

    dir_path: Path | str
    for dir_path in chain(build_dir, egg_info_dir, dist_dir):  # type: ignore[assignment]
        if Path(dir_path).is_dir():
            shutil.rmtree(dir_path)

    print_info("Cleaning after build project - finished.")


def _remove_whls(path: str | Path = "dist") -> None:
    """Remove all whl files from the specified path.

    Args:
        path (str, optional): Path to whl files. Defaults to 'dist'.
    """
    print_info("Removing of the whl files started.")

    for whl_file in Path().glob(f"{path}/*.whl"):
        Path(whl_file).unlink()

    print_info("Removing finished.")


def _build_docker_image(path: str, tag: str) -> None:
    """Build a Docker image.

    Args:
        path (str): The path to the Dockerfile to be built.
        tag (str): The tag to be used.
    """
    print_info(f"Docker image building has begun with tag: {tag}")

    docker_build = subprocess.Popen(["docker", "build", "-t", tag, path]).wait()

    if docker_build != 0:
        print_error("Something went wrong while building!")
        sys.exit(FAILURE_CODE)

    print_info(f"Docker image was built with tag: {tag}")


def _copy_project_files_to_docker_app(path: str | Path = "dist") -> None:
    """Copy necessary project files to the build directory.

    This function copies the 'pyproject.toml' and 'uv.lock' files from the root
    directory of the project to the build directory. This is essential for
    ensuring that the Docker build process has access to the correct dependencies
    and project configuration.

    Args:
        path (str, Path): Path where to copy files. Defaults to 'dist'.
    """
    print_info("Copying project files to build directory - started.")
    source_files = ["pyproject.toml", "uv.lock"]

    for file_name in source_files:
        source_path = Path(file_name)
        destination_path = Path(path) / file_name

        if source_path.exists():
            shutil.copy(source_path, destination_path)
            print_info(f"Copied {file_name} to {destination_path}")
        else:
            print_warning(f"Source file {file_name} does not exist and cannot be copied.")

    print_info("Copying project files to build directory - finished.")


def _remove_project_files_from_docker_app(path: str | Path = "dist") -> None:
    """Remove project files from the build directory.

    This function removes the 'pyproject.toml' and 'uv.lock' files from the
    build directory after the Docker build process is complete. This helps
    to keep the build directory clean and free from unnecessary files.

    Args:
        path (str, Path): Path where to remove files. Defaults to 'dist'.
    """
    print_info("Removing project files from build directory - started.")
    files_to_remove = ["pyproject.toml", "uv.lock"]

    for file_name in files_to_remove:
        file_path = Path(path) / file_name

        if file_path.exists():
            file_path.unlink()
            print_info(f"Removed {file_name} from {file_path}")
        else:
            print_warning(f"File {file_name} does not exist in {file_path} and cannot be removed.")

    print_info("Removing project files from build directory - finished.")


@app.command()
def build_app(
    tag: str = typer.Option("latest", help="Tag for a built web application container."),
    *,
    clean: bool = typer.Option(default=True, help="Cleaning after building."),
) -> None:
    """Build a web application container."""
    print_info("Build app container - started.")
    app_directory = Path("docker", "app")
    clean_up(None)  # type: ignore[arg-type]
    _remove_whls(app_directory)
    setup_project(str(app_directory))
    _copy_project_files_to_docker_app(app_directory)

    _build_docker_image(str(app_directory), f"{DOCKER_REGISTRY_PATH_APP}:{tag}")

    if clean:
        clean_up(None)  # type: ignore[arg-type]
        _remove_whls(app_directory)
        _remove_project_files_from_docker_app(app_directory)

    print_info("Build app container - finished.")


@app.command()
def build_nginx(tag: str = typer.Option("latest", help="Tag for a built Nginx container.")) -> None:
    """Build an Nginx container."""
    print_info("Build nginx container - started.")

    self_signed_certificate = subprocess.Popen(
        [
            "openssl",
            "req",
            "-x509",
            "-sha256",
            "-nodes",
            "-days",
            "365",
            "-subj",
            "/C=PL/ST=ST/L=L/O=GameList/CN=GameList",
            "-newkey",
            "rsa:2048",
            "-keyout",
            "docker/nginx/ssl/nginx-key.key",
            "-out",
            "docker/nginx/ssl/nginx-cert.crt",
        ],
    ).wait()
    if self_signed_certificate != 0:
        print_error("Something went wrong while creating self-signed certificate!")
        sys.exit(FAILURE_CODE)

    nginx_directory = Path("docker", "nginx")
    _build_docker_image(str(nginx_directory), f"{DOCKER_REGISTRY_PATH_NGINX}:{tag}")

    print_info("Build nginx container - finished.")


@app.command()
def build_images(tag: str = typer.Option("latest", help="Tag for built containers.")) -> None:
    """Build all containers for a project (app, Nginx)."""
    build_app(tag, clean=True)
    build_nginx(tag)


def _push_docker_image(repository: str, tag: str) -> None:
    """Push docker image to the GitHub repository.

    Args:
        repository (str): The name of the repository to be pushed.
        tag (str): The tag to be pushed.
    """
    print_info(f"Pushing docker image to the registry with tag: {tag}")

    push_response = subprocess.Popen(["docker", "push", f"{repository}:{tag}"]).wait()

    if push_response != 0:
        print_error("Something went wrong while pushing!")
        sys.exit(FAILURE_CODE)

    print_info(f"Docker image was pushed to the registry with tag: {tag}")


@app.command()
def push_app(tag: str = typer.Option("latest", help="Tag for a pushed web container.")) -> None:
    """Push a docker web container to the registry."""
    print_info("Pushing app package ...")
    _push_docker_image(DOCKER_REGISTRY_PATH_APP, tag)


@app.command()
def push_nginx(tag: str = typer.Option("latest", help="Tag for a pushed Nginx container.")) -> None:
    """Push a docker Nginx container to the registry."""
    print_info("Pushing nginx package ...")
    _push_docker_image(DOCKER_REGISTRY_PATH_NGINX, tag)


@app.command()
def push_images(tag: str = typer.Option("latest", help="Tag for built containers.")) -> None:
    """Push all built containers(web, Nginx) to the registry."""
    push_app(tag)
    push_nginx(tag)


@app.command()
def docker_up() -> None:
    """Docker-compose up with default configuration."""
    docker_compose_path = Path("docker", "docker-compose.yml")
    subprocess.Popen(["docker", "compose", "-f", f"{docker_compose_path}", "up"]).wait()


@app.command()
def docker_build_and_up() -> None:
    """Build all images and docker-compose up with default configuration."""
    build_images("latest")
    docker_up()


if __name__ == "__main__":
    app()
