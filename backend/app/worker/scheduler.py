"""Celery Beat schedule configuration."""

from __future__ import annotations

from celery.schedules import crontab

from app.worker.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "scrape-all-morning": {
        "task": "scrape_all_sources",
        "schedule": crontab(hour=6, minute=0),
    },
    "scrape-all-evening": {
        "task": "scrape_all_sources",
        "schedule": crontab(hour=18, minute=0),
    },
    "check-inactive": {
        "task": "check_inactive_listings",
        "schedule": crontab(hour=3, minute=0),
    },
}
