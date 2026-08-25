"""This package contains all the base functionalities used across all applications."""

from game_list.game_list.celery import app as celery_app

__all__ = ("celery_app",)
