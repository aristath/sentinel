"""Service locator for finding and connecting to services."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union, cast

import grpc
import yaml  # type: ignore[import-untyped]

from app.infrastructure.http_clients.gateway_client import GatewayHTTPClient
from app.infrastructure.http_clients.optimization_client import OptimizationHTTPClient
from app.infrastructure.http_clients.planning_client import PlanningHTTPClient
from app.infrastructure.http_clients.portfolio_client import PortfolioHTTPClient
from app.infrastructure.http_clients.scoring_client import ScoringHTTPClient
from app.infrastructure.http_clients.trading_client import TradingHTTPClient
from app.infrastructure.http_clients.universe_client import UniverseHTTPClient
from app.infrastructure.service_discovery.device_config import DeviceInfo


@dataclass
class ServiceConfig:
    """Service configuration."""

    name: str
    mode: str  # "local" or "remote"
    device_id: str
    port: int
    client_config: Dict[str, Any]
    health_check_config: Dict[str, Any]


@dataclass
class TLSConfig:
    """TLS/mTLS configuration."""

    enabled: bool
    mutual: bool
    ca_cert: str
    server_cert: str
    server_key: str
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
    server_hostname_override: Optional[str] = None


@dataclass
class ServiceLocation:
    """Service location information."""

    name: str
    mode: str  # "local" or "remote"
    address: str  # "localhost" or IP address
    port: int
    timeout_seconds: int
    max_retries: int
    retry_backoff_ms: int


class ServiceLocator:
    """
    Locates services and provides connection information.

    Handles both local (in-process) and remote (gRPC) services.
    """

    def __init__(self, services_config_path: Optional[str] = None):
        """
        Initialize service locator.

        Args:
            services_config_path: Path to services.yaml, or None for default
        """
        services_config_path_resolved: str
        if services_config_path is None:
            app_root = Path(__file__).parent.parent.parent
            services_config_path_resolved = str(app_root / "config" / "services.yaml")
        else:
            services_config_path_resolved = services_config_path

        # Allow override via environment variable
        services_config_path_resolved = os.getenv(
            "SERVICES_CONFIG_PATH", services_config_path_resolved
        )

        with open(services_config_path_resolved, "r") as f:
            self.config = yaml.safe_load(f)

        self.deployment_mode = self.config["deployment"]["mode"]
        self.services = self.config["services"]
        self.devices = {
            dev_id: DeviceInfo(id=dev_id, address=info["address"])
            for dev_id, info in self.config["devices"].items()
        }

        # Load TLS configuration
        self.tls_config = self._load_tls_config()
        self.project_root = Path(__file__).parent.parent.parent.parent

    def _load_tls_config(self) -> Optional[TLSConfig]:
        """Load TLS configuration from services.yaml."""
        tls_conf = self.config.get("tls", {})
        if not tls_conf.get("enabled", False):
            return None

        return TLSConfig(
            enabled=tls_conf.get("enabled", False),
            mutual=tls_conf.get("mutual", False),
            ca_cert=tls_conf.get("ca_cert", "certs/ca-cert.pem"),
            server_cert=tls_conf.get("server_cert", "certs/server-cert.pem"),
            server_key=tls_conf.get("server_key", "certs/server-key.pem"),
            client_cert=tls_conf.get("client_cert"),
            client_key=tls_conf.get("client_key"),
            server_hostname_override=tls_conf.get("server_hostname_override"),
        )

    def get_service_location(self, service_name: str) -> ServiceLocation:
        """
        Get location info for a service.

        Args:
            service_name: Name of service (e.g., "planning")

        Returns:
            ServiceLocation with connection details

        Raises:
            ValueError: If service not found in config
        """
        if service_name not in self.services:
            raise ValueError(f"Service '{service_name}' not found in config")

        svc = self.services[service_name]
        mode = svc["mode"]
        device_id = svc["device_id"]
        port = svc["port"]

        # Get device address
        if mode == "local":
            address = "localhost"
        else:
            if device_id not in self.devices:
                raise ValueError(
                    f"Device '{device_id}' not found for service '{service_name}'"
                )
            address = self.devices[device_id].address

        # Get client config
        client_config = svc.get("client", {})

        return ServiceLocation(
            name=service_name,
            mode=mode,
            address=address,
            port=port,
            timeout_seconds=client_config.get("timeout_seconds", 30),
            max_retries=client_config.get("max_retries", 3),
            retry_backoff_ms=client_config.get("retry_backoff_ms", 1000),
        )

    def create_channel(self, service_name: str) -> grpc.aio.Channel:
        """
        Create gRPC channel for a service.

        Supports both insecure channels (local/development) and
        secure channels with TLS/mTLS (production/distributed).

        Args:
            service_name: Name of service

        Returns:
            Async gRPC channel (insecure or secure based on TLS config)
        """
        location = self.get_service_location(service_name)

        target = f"{location.address}:{location.port}"

        # Create channel options
        options: list[tuple[str, Any]] = [
            ("grpc.keepalive_time_ms", 30000),
            ("grpc.keepalive_timeout_ms", 10000),
            ("grpc.keepalive_permit_without_calls", 1),
            ("grpc.http2.max_pings_without_data", 0),
        ]

        # Use TLS if configured
        if self.tls_config and self.tls_config.enabled:
            credentials = self._create_channel_credentials()

            # Override server hostname if specified (useful for self-signed certs)
            if self.tls_config.server_hostname_override:
                options.append(
                    (
                        "grpc.ssl_target_name_override",
                        self.tls_config.server_hostname_override,
                    )
                )

            channel = grpc.aio.secure_channel(target, credentials, options=options)
        else:
            # Insecure channel for local mode or when TLS is disabled
            channel = grpc.aio.insecure_channel(target, options=options)

        return channel

    def create_http_client(self, service_name: str) -> Union[
        UniverseHTTPClient,
        PortfolioHTTPClient,
        TradingHTTPClient,
        ScoringHTTPClient,
        OptimizationHTTPClient,
        PlanningHTTPClient,
        GatewayHTTPClient,
    ]:
        """
        Create HTTP client for a service.

        Args:
            service_name: Name of service

        Returns:
            HTTP client instance for the service

        Raises:
            ValueError: If service name is unknown
        """
        location = self.get_service_location(service_name)

        # Build base URL
        base_url = f"http://{location.address}:{location.port}"

        # Create appropriate client based on service name
        client_classes = {
            "universe": UniverseHTTPClient,
            "portfolio": PortfolioHTTPClient,
            "trading": TradingHTTPClient,
            "scoring": ScoringHTTPClient,
            "optimization": OptimizationHTTPClient,
            "planning": PlanningHTTPClient,
            "gateway": GatewayHTTPClient,
        }

        if service_name not in client_classes:
            raise ValueError(f"Unknown service: {service_name}")

        client_class = client_classes[service_name]
        # Type cast is safe because we validate service_name above
        return cast(
            Union[
                UniverseHTTPClient,
                PortfolioHTTPClient,
                TradingHTTPClient,
                ScoringHTTPClient,
                OptimizationHTTPClient,
                PlanningHTTPClient,
                GatewayHTTPClient,
            ],
            client_class(
                base_url=base_url,
                service_name=service_name,
                timeout=float(location.timeout_seconds),
            ),
        )

    def _create_channel_credentials(self) -> grpc.ChannelCredentials:
        """
        Create gRPC channel credentials for TLS/mTLS.

        Returns:
            Channel credentials with CA cert and optional client cert

        Raises:
            FileNotFoundError: If certificate files don't exist
        """
        if not self.tls_config:
            raise ValueError("TLS config not loaded")

        # Resolve certificate paths (support both relative and absolute)
        ca_cert_path = self._resolve_cert_path(self.tls_config.ca_cert)

        # Read CA certificate
        with open(ca_cert_path, "rb") as f:
            ca_cert = f.read()

        # mTLS: Include client certificate and key
        if self.tls_config.mutual:
            if not self.tls_config.client_cert or not self.tls_config.client_key:
                raise ValueError(
                    "mTLS enabled but client_cert/client_key not configured"
                )

            client_cert_path = self._resolve_cert_path(self.tls_config.client_cert)
            client_key_path = self._resolve_cert_path(self.tls_config.client_key)

            with open(client_cert_path, "rb") as f:
                client_cert = f.read()

            with open(client_key_path, "rb") as f:
                client_key = f.read()

            credentials = grpc.ssl_channel_credentials(
                root_certificates=ca_cert,
                private_key=client_key,
                certificate_chain=client_cert,
            )
        else:
            # TLS only: Server authentication
            credentials = grpc.ssl_channel_credentials(root_certificates=ca_cert)

        return credentials

    def _resolve_cert_path(self, cert_path: str) -> Path:
        """
        Resolve certificate path (supports relative and absolute paths).

        Args:
            cert_path: Certificate path from config

        Returns:
            Absolute Path to certificate
        """
        path = Path(cert_path)

        # If absolute, use as-is
        if path.is_absolute():
            return path

        # Otherwise, resolve relative to project root
        return self.project_root / cert_path

    def create_server_credentials(self) -> Optional[grpc.ServerCredentials]:
        """
        Create gRPC server credentials for TLS/mTLS.

        Returns:
            Server credentials, or None if TLS is disabled

        Raises:
            FileNotFoundError: If certificate files don't exist
        """
        if not self.tls_config or not self.tls_config.enabled:
            return None

        # Resolve certificate paths
        server_cert_path = self._resolve_cert_path(self.tls_config.server_cert)
        server_key_path = self._resolve_cert_path(self.tls_config.server_key)

        # Read server certificate and key
        with open(server_cert_path, "rb") as f:
            server_cert = f.read()

        with open(server_key_path, "rb") as f:
            server_key = f.read()

        # mTLS: Require client certificates
        if self.tls_config.mutual:
            ca_cert_path = self._resolve_cert_path(self.tls_config.ca_cert)

            with open(ca_cert_path, "rb") as f:
                ca_cert = f.read()

            credentials = grpc.ssl_server_credentials(
                [(server_key, server_cert)],
                root_certificates=ca_cert,
                require_client_auth=True,
            )
        else:
            # TLS only: No client authentication required
            credentials = grpc.ssl_server_credentials([(server_key, server_cert)])

        return credentials

    def add_server_port(self, server: grpc.aio.Server, service_name: str) -> str:
        """
        Add port to gRPC server with appropriate security.

        Automatically uses secure or insecure port based on TLS config.

        Args:
            server: gRPC async server instance
            service_name: Name of service (for getting port from config)

        Returns:
            Address string (host:port)
        """
        location = self.get_service_location(service_name)

        # Get device config for bind address
        from app.infrastructure.service_discovery import load_device_config

        device_config = load_device_config()
        address = f"{device_config.bind_address}:{location.port}"

        # Add port with or without TLS
        credentials = self.create_server_credentials()
        if credentials:
            server.add_secure_port(address, credentials)
        else:
            server.add_insecure_port(address)

        return address

    def is_service_local(self, service_name: str) -> bool:
        """Check if service runs locally (in-process)."""
        location = self.get_service_location(service_name)
        return location.mode == "local"

    def get_all_local_services(self) -> list[str]:
        """Get list of services that run locally on this device."""
        return [name for name, svc in self.services.items() if svc["mode"] == "local"]


# Global service locator instance
_service_locator: Optional[ServiceLocator] = None


def get_service_locator() -> ServiceLocator:
    """Get global service locator instance (singleton)."""
    global _service_locator
    if _service_locator is None:
        _service_locator = ServiceLocator()
    return _service_locator


def reset_service_locator():
    """Reset service locator (for testing)."""
    global _service_locator
    _service_locator = None
