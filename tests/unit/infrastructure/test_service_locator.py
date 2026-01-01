"""Unit tests for ServiceLocator."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import grpc
import pytest
import yaml  # type: ignore[import-untyped]

from app.infrastructure.service_discovery.service_locator import (
    ServiceLocator,
    get_service_locator,
    reset_service_locator,
)


@pytest.fixture
def mock_services_config():
    """Create mock services.yaml configuration."""
    return {
        "deployment": {"mode": "distributed"},
        "devices": {
            "arduino1": {"address": "192.168.1.100"},
            "arduino2": {"address": "192.168.1.101"},
        },
        "services": {
            "planning": {
                "mode": "local",
                "device_id": "arduino1",
                "port": 50051,
                "client": {
                    "timeout_seconds": 30,
                    "max_retries": 3,
                    "retry_backoff_ms": 1000,
                },
            },
            "scoring": {
                "mode": "remote",
                "device_id": "arduino2",
                "port": 50052,
                "client": {
                    "timeout_seconds": 60,
                    "max_retries": 5,
                    "retry_backoff_ms": 2000,
                },
            },
        },
        "tls": {
            "enabled": False,
        },
    }


@pytest.fixture
def mock_services_config_with_tls():
    """Create mock services.yaml with TLS enabled."""
    return {
        "deployment": {"mode": "distributed"},
        "devices": {"arduino1": {"address": "192.168.1.100"}},
        "services": {
            "planning": {
                "mode": "local",
                "device_id": "arduino1",
                "port": 50051,
            }
        },
        "tls": {
            "enabled": True,
            "mutual": False,
            "ca_cert": "certs/ca-cert.pem",
            "server_cert": "certs/server-cert.pem",
            "server_key": "certs/server-key.pem",
        },
    }


@pytest.fixture
def mock_services_config_with_mtls():
    """Create mock services.yaml with mTLS enabled."""
    return {
        "deployment": {"mode": "distributed"},
        "devices": {"arduino1": {"address": "192.168.1.100"}},
        "services": {
            "planning": {
                "mode": "local",
                "device_id": "arduino1",
                "port": 50051,
            }
        },
        "tls": {
            "enabled": True,
            "mutual": True,
            "ca_cert": "certs/ca-cert.pem",
            "server_cert": "certs/server-cert.pem",
            "server_key": "certs/server-key.pem",
            "client_cert": "certs/client-cert.pem",
            "client_key": "certs/client-key.pem",
            "server_hostname_override": "localhost",
        },
    }


@pytest.fixture
def temp_config_file(mock_services_config):
    """Create temporary services.yaml file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(mock_services_config, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def temp_config_file_with_tls(mock_services_config_with_tls):
    """Create temporary services.yaml with TLS enabled."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(mock_services_config_with_tls, f)
        temp_path = f.name

    yield temp_path

    os.unlink(temp_path)


@pytest.fixture
def temp_config_file_with_mtls(mock_services_config_with_mtls):
    """Create temporary services.yaml with mTLS enabled."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(mock_services_config_with_mtls, f)
        temp_path = f.name

    yield temp_path

    os.unlink(temp_path)


@pytest.fixture
def temp_cert_files():
    """Create temporary certificate files."""
    temp_dir = tempfile.mkdtemp()
    certs_dir = Path(temp_dir) / "certs"
    certs_dir.mkdir()

    # Create mock certificate files
    (certs_dir / "ca-cert.pem").write_text("MOCK CA CERT")
    (certs_dir / "server-cert.pem").write_text("MOCK SERVER CERT")
    (certs_dir / "server-key.pem").write_text("MOCK SERVER KEY")
    (certs_dir / "client-cert.pem").write_text("MOCK CLIENT CERT")
    (certs_dir / "client-key.pem").write_text("MOCK CLIENT KEY")

    yield temp_dir

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir)


def test_service_locator_initialization(temp_config_file):
    """Test ServiceLocator initialization."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    assert locator.deployment_mode == "distributed"
    assert "planning" in locator.services
    assert "scoring" in locator.services
    assert "arduino1" in locator.devices
    assert "arduino2" in locator.devices


def test_service_locator_env_override(temp_config_file):
    """Test environment variable override for config path."""
    os.environ["SERVICES_CONFIG_PATH"] = temp_config_file

    try:
        locator = ServiceLocator()
        assert locator.deployment_mode == "distributed"
    finally:
        del os.environ["SERVICES_CONFIG_PATH"]


def test_get_service_location_local(temp_config_file):
    """Test getting location for local service."""
    locator = ServiceLocator(services_config_path=temp_config_file)
    location = locator.get_service_location("planning")

    assert location.name == "planning"
    assert location.mode == "local"
    assert location.address == "localhost"
    assert location.port == 50051
    assert location.timeout_seconds == 30
    assert location.max_retries == 3
    assert location.retry_backoff_ms == 1000


def test_get_service_location_remote(temp_config_file):
    """Test getting location for remote service."""
    locator = ServiceLocator(services_config_path=temp_config_file)
    location = locator.get_service_location("scoring")

    assert location.name == "scoring"
    assert location.mode == "remote"
    assert location.address == "192.168.1.101"
    assert location.port == 50052
    assert location.timeout_seconds == 60
    assert location.max_retries == 5
    assert location.retry_backoff_ms == 2000


def test_get_service_location_not_found(temp_config_file):
    """Test error when service not found."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    with pytest.raises(ValueError, match="Service 'nonexistent' not found"):
        locator.get_service_location("nonexistent")


def test_get_service_location_device_not_found(temp_config_file):
    """Test error when device not found for remote service."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    # Add service with non-existent device
    locator.services["invalid"] = {
        "mode": "remote",
        "device_id": "nonexistent",
        "port": 50053,
    }

    with pytest.raises(ValueError, match="Device 'nonexistent' not found"):
        locator.get_service_location("invalid")


def test_load_tls_config_disabled(temp_config_file):
    """Test TLS config loading when disabled."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    assert locator.tls_config is None


def test_load_tls_config_enabled(temp_config_file_with_tls):
    """Test TLS config loading when enabled."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_tls)

    assert locator.tls_config is not None
    assert locator.tls_config.enabled is True
    assert locator.tls_config.mutual is False
    assert locator.tls_config.ca_cert == "certs/ca-cert.pem"
    assert locator.tls_config.server_cert == "certs/server-cert.pem"
    assert locator.tls_config.server_key == "certs/server-key.pem"


def test_load_tls_config_mtls(temp_config_file_with_mtls):
    """Test TLS config loading with mTLS enabled."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_mtls)

    assert locator.tls_config is not None
    assert locator.tls_config.enabled is True
    assert locator.tls_config.mutual is True
    assert locator.tls_config.client_cert == "certs/client-cert.pem"
    assert locator.tls_config.client_key == "certs/client-key.pem"
    assert locator.tls_config.server_hostname_override == "localhost"


def test_create_insecure_channel(temp_config_file):
    """Test creating insecure gRPC channel."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    channel = locator.create_channel("planning")

    assert isinstance(channel, grpc.aio.Channel)
    # Channel created, will be closed when test ends


def test_create_secure_channel_with_tls(temp_config_file_with_tls, temp_cert_files):
    """Test creating secure channel with TLS."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_tls)

    # Override project root to use temp certs
    locator.project_root = Path(temp_cert_files)

    channel = locator.create_channel("planning")

    assert isinstance(channel, grpc.aio.Channel)


def test_create_secure_channel_with_mtls(temp_config_file_with_mtls, temp_cert_files):
    """Test creating secure channel with mTLS."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_mtls)

    # Override project root to use temp certs
    locator.project_root = Path(temp_cert_files)

    channel = locator.create_channel("planning")

    assert isinstance(channel, grpc.aio.Channel)


def test_resolve_cert_path_relative(temp_config_file):
    """Test certificate path resolution for relative paths."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    resolved = locator._resolve_cert_path("certs/ca-cert.pem")

    assert resolved.is_absolute()
    assert str(resolved).endswith("certs/ca-cert.pem")


def test_resolve_cert_path_absolute(temp_config_file):
    """Test certificate path resolution for absolute paths."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    absolute_path = "/tmp/certs/ca-cert.pem"
    resolved = locator._resolve_cert_path(absolute_path)

    assert resolved == Path(absolute_path)
    assert resolved.is_absolute()


def test_create_channel_credentials_tls(temp_config_file_with_tls, temp_cert_files):
    """Test creating channel credentials for TLS."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_tls)
    locator.project_root = Path(temp_cert_files)

    credentials = locator._create_channel_credentials()

    assert isinstance(credentials, grpc.ChannelCredentials)


def test_create_channel_credentials_mtls(temp_config_file_with_mtls, temp_cert_files):
    """Test creating channel credentials for mTLS."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_mtls)
    locator.project_root = Path(temp_cert_files)

    credentials = locator._create_channel_credentials()

    assert isinstance(credentials, grpc.ChannelCredentials)


def test_create_channel_credentials_no_tls_config(temp_config_file):
    """Test error when creating credentials without TLS config."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    with pytest.raises(ValueError, match="TLS config not loaded"):
        locator._create_channel_credentials()


def test_create_channel_credentials_mtls_missing_client_cert(
    temp_config_file_with_tls, temp_cert_files
):
    """Test error when mTLS enabled but client cert missing."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_tls)
    locator.project_root = Path(temp_cert_files)

    # Enable mutual TLS but don't provide client cert
    assert locator.tls_config is not None
    locator.tls_config.mutual = True
    locator.tls_config.client_cert = None

    with pytest.raises(ValueError, match="mTLS enabled but client_cert"):
        locator._create_channel_credentials()


def test_create_server_credentials_disabled(temp_config_file):
    """Test server credentials when TLS disabled."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    credentials = locator.create_server_credentials()

    assert credentials is None


def test_create_server_credentials_tls(temp_config_file_with_tls, temp_cert_files):
    """Test creating server credentials with TLS."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_tls)
    locator.project_root = Path(temp_cert_files)

    credentials = locator.create_server_credentials()

    assert isinstance(credentials, grpc.ServerCredentials)


def test_create_server_credentials_mtls(temp_config_file_with_mtls, temp_cert_files):
    """Test creating server credentials with mTLS."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_mtls)
    locator.project_root = Path(temp_cert_files)

    credentials = locator.create_server_credentials()

    assert isinstance(credentials, grpc.ServerCredentials)


@patch("app.infrastructure.service_discovery.load_device_config")
def test_add_server_port_insecure(mock_load_device, temp_config_file):
    """Test adding insecure port to server."""
    # Mock device config
    mock_device = MagicMock()
    mock_device.bind_address = "0.0.0.0"  # nosec B104
    mock_load_device.return_value = mock_device

    locator = ServiceLocator(services_config_path=temp_config_file)
    mock_server = MagicMock()

    address = locator.add_server_port(mock_server, "planning")

    assert address == "0.0.0.0:50051"
    mock_server.add_insecure_port.assert_called_once_with("0.0.0.0:50051")


@patch("app.infrastructure.service_discovery.load_device_config")
def test_add_server_port_secure(
    mock_load_device, temp_config_file_with_tls, temp_cert_files
):
    """Test adding secure port to server."""
    # Mock device config
    mock_device = MagicMock()
    mock_device.bind_address = "0.0.0.0"  # nosec B104
    mock_load_device.return_value = mock_device

    locator = ServiceLocator(services_config_path=temp_config_file_with_tls)
    locator.project_root = Path(temp_cert_files)
    mock_server = MagicMock()

    address = locator.add_server_port(mock_server, "planning")

    assert address == "0.0.0.0:50051"
    mock_server.add_secure_port.assert_called_once()


def test_is_service_local(temp_config_file):
    """Test checking if service is local."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    assert locator.is_service_local("planning") is True
    assert locator.is_service_local("scoring") is False


def test_get_all_local_services(temp_config_file):
    """Test getting all local services."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    local_services = locator.get_all_local_services()

    assert "planning" in local_services
    assert "scoring" not in local_services


def test_singleton_pattern(temp_config_file):
    """Test service locator singleton pattern."""
    reset_service_locator()

    # Set environment to use temp config
    os.environ["SERVICES_CONFIG_PATH"] = temp_config_file

    try:
        locator1 = get_service_locator()
        locator2 = get_service_locator()

        # Same instance
        assert locator1 is locator2

        # Reset creates new instance
        reset_service_locator()
        locator3 = get_service_locator()

        assert locator1 is not locator3
    finally:
        del os.environ["SERVICES_CONFIG_PATH"]
        reset_service_locator()


def test_channel_options_configured(temp_config_file):
    """Test that channel options are properly configured."""
    locator = ServiceLocator(services_config_path=temp_config_file)

    # Mock grpc to capture options
    with patch("grpc.aio.insecure_channel") as mock_insecure:
        locator.create_channel("planning")

        # Verify called with options
        mock_insecure.assert_called_once()
        call_args = mock_insecure.call_args

        # Check options include keepalive settings
        options = call_args.kwargs.get("options", [])
        option_names = [opt[0] for opt in options]

        assert "grpc.keepalive_time_ms" in option_names
        assert "grpc.keepalive_timeout_ms" in option_names
        assert "grpc.keepalive_permit_without_calls" in option_names


def test_hostname_override_in_channel(temp_config_file_with_mtls, temp_cert_files):
    """Test server hostname override in secure channel."""
    locator = ServiceLocator(services_config_path=temp_config_file_with_mtls)
    locator.project_root = Path(temp_cert_files)

    with patch("grpc.aio.secure_channel") as mock_secure:
        locator.create_channel("planning")

        # Verify called with hostname override option
        mock_secure.assert_called_once()
        call_args = mock_secure.call_args

        options = call_args.kwargs.get("options", [])
        option_dict = dict(options)

        assert "grpc.ssl_target_name_override" in option_dict
        assert option_dict["grpc.ssl_target_name_override"] == "localhost"
