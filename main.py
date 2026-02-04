#!/usr/bin/env python3
"""
Sentinel - Entry point for running the application.

Usage:
    python main.py          # Run web server only
    python main.py --all    # Run web server + scheduler
"""

import argparse
import asyncio
import logging

import uvicorn

from sentinel import Broker, Database, Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def init_services():
    """Initialize all services."""
    logger.info("Initializing services...")

    db = Database()
    await db.connect()
    logger.info("Database connected")

    settings = Settings()
    await settings.init_defaults()
    logger.info("Settings initialized")

    broker = Broker()
    if await broker.connect():
        logger.info("Broker connected")
    else:
        logger.warning("Broker not connected (missing credentials?)")


async def run_scheduler():
    """Run the background scheduler."""
    # Note: SyncScheduler requires db, queue, registry, and market_checker
    # For standalone scheduler, use --all flag which uses app.py's lifespan
    raise NotImplementedError("Use --all flag to run scheduler with web server")


def main():
    parser = argparse.ArgumentParser(description="Sentinel Portfolio Management")
    parser.add_argument("--all", action="store_true", help="Run scheduler alongside web server")
    parser.add_argument("--scheduler-only", action="store_true", help="Run scheduler only (no web server)")
    parser.add_argument("--host", default="::", help="Web server host")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    args = parser.parse_args()

    # Do not run init_services() here when starting the web server: uvicorn uses a
    # different event loop, so a DB connection created here would be invalid in
    # request handlers. The app's lifespan (sentinel.app) connects the DB in the
    # same loop that serves requests.

    if args.scheduler_only:
        logger.info("Running scheduler only")
        asyncio.run(run_scheduler())
    elif args.all:
        # Run both web server and scheduler
        logger.info("Running web server and scheduler")

        async def run_all():
            # Note: Scheduler and LED controller are started by app.py's lifespan
            config = uvicorn.Config("sentinel.app:app", host=args.host, port=args.port, log_level="info")
            server = uvicorn.Server(config)
            await server.serve()

        asyncio.run(run_all())
    else:
        # Web server only
        logger.info(f"Running web server on {args.host}:{args.port}")
        uvicorn.run("sentinel.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
