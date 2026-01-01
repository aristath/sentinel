"""Planning service server entrypoint."""

import asyncio
import logging
import signal
from concurrent import futures

import grpc

from contracts import planning_pb2_grpc  # type: ignore[attr-defined]
from app.infrastructure.service_discovery import load_device_config, get_service_locator
from services.planning.grpc_servicer import PlanningServicer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def serve():
    """Start the gRPC server."""
    # Load configuration
    device_config = load_device_config()
    service_locator = get_service_locator()
    planning_location = service_locator.get_service_location("planning")

    # Create gRPC server
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=device_config.max_workers)
    )

    # Add servicer to server
    planning_pb2_grpc.add_PlanningServiceServicer_to_server(PlanningServicer(), server)

    # Bind to address
    address = f"{device_config.bind_address}:{planning_location.port}"
    server.add_insecure_port(address)

    # Start server
    logger.info(f"Starting Planning service on {address}")
    await server.start()
    logger.info("Planning service started successfully")

    # Setup graceful shutdown
    async def shutdown(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        await server.stop(grace=5)
        logger.info("Server stopped")

    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))

    # Wait for termination
    await server.wait_for_termination()


def main():
    """Main entry point."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
