"""Portfolio service server entrypoint."""

import asyncio
import logging
import signal
from concurrent import futures

import grpc

from contracts import portfolio_pb2_grpc  # type: ignore[attr-defined]
from app.infrastructure.service_discovery import load_device_config, get_service_locator
from services.portfolio.grpc_servicer import PortfolioServicer

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

    # Create gRPC server
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=device_config.max_workers)
    )

    # Add servicer to server
    portfolio_pb2_grpc.add_PortfolioServiceServicer_to_server(
        PortfolioServicer(), server
    )

    # Bind to address (with TLS support if configured)
    address = service_locator.add_server_port(server, "portfolio")

    # Start server
    tls_status = "with TLS" if service_locator.tls_config else "without TLS"
    logger.info(f"Starting Portfolio service on {address} ({tls_status})")
    await server.start()
    logger.info("Portfolio service started successfully")

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
