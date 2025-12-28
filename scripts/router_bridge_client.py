"""Router Bridge client for Arduino Uno Q.

Provides a Python interface to call functions exposed by the MCU sketch
via Router Bridge (msgpack RPC over Unix socket).
"""

import logging
import socket
import struct
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Router Bridge socket path
ROUTER_BRIDGE_SOCKET = "/var/run/arduino-router.sock"

try:
    import msgpack
except ImportError:
    msgpack = None
    logger.warning("msgpack not available - Router Bridge client will not work")


class RouterBridgeClient:
    """Client for communicating with MCU via Router Bridge."""

    def __init__(self, socket_path: str = ROUTER_BRIDGE_SOCKET):
        """Initialize Router Bridge client.

        Args:
            socket_path: Path to Router Bridge Unix socket
        """
        self.socket_path = socket_path
        if msgpack is None:
            raise ImportError("msgpack package is required for Router Bridge client")

    def _connect(self) -> socket.socket:
        """Create and return a connected socket to Router Bridge."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.socket_path)
            return sock
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Router Bridge at {self.socket_path}: {e}") from e

    def call(self, function_name: str, *args: Any, timeout: float = 5.0) -> Optional[Any]:
        """Call a function on the MCU via Router Bridge.

        Args:
            function_name: Name of the function to call (must be registered via Bridge.provide)
            *args: Arguments to pass to the function
            timeout: Timeout in seconds for the RPC call

        Returns:
            Function return value, or None if function returns void

        Raises:
            ConnectionError: If connection to Router Bridge fails
            TimeoutError: If call times out
            RuntimeError: If RPC call fails
        """
        if msgpack is None:
            raise ImportError("msgpack package is required")

        sock = self._connect()
        try:
            sock.settimeout(timeout)

            # Router Bridge RPClite protocol format: [type, id, method, params]
            # type=1 for request, id=message_id, method=function_name, params=args as list
            import random
            message_id = random.randint(1, 999999)  # Use random ID to avoid conflicts
            message = [1, message_id, function_name, list(args)]

            # Pack message with msgpack (no length prefix - msgpack is self-describing)
            packed = msgpack.packb(message, use_bin_type=True)

            # Send message directly (no length prefix)
            sock.sendall(packed)

            # Receive response using Unpacker for proper streaming
            # Router Bridge sends response as msgpack without length prefix
            unpacker = msgpack.Unpacker(raw=False)
            response = None
            max_attempts = 100

            for attempt in range(max_attempts):
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        if attempt == 0:
                            raise RuntimeError("No response from Router Bridge")
                        break
                    unpacker.feed(chunk)
                    # Try to extract a complete message
                    for msg in unpacker:
                        response = msg
                        break
                    if response is not None:
                        break
                except socket.timeout:
                    if attempt == 0:
                        raise RuntimeError("No response from Router Bridge (timeout)")
                    break
                except Exception as e:
                    logger.debug(f"Error reading response (attempt {attempt}): {e}")
                    continue

            if response is None:
                raise RuntimeError("Could not read complete response from Router Bridge")

            # Router Bridge RPClite response format: [type, id, error, result]
            # type=2 for response, id=message_id, error=error object, result=return value
            if len(response) != 4:
                raise RuntimeError(f"Invalid response format: expected 4 elements, got {len(response)}: {response}")

            resp_type, resp_id, error, result = response

            if resp_id != message_id:
                raise RuntimeError(f"Response ID mismatch: expected {message_id}, got {resp_id}")

            if error is not None:
                raise RuntimeError(f"Router Bridge error: {error}")

            return result

        except socket.timeout as e:
            raise TimeoutError(f"Router Bridge call timed out after {timeout}s") from e
        except Exception as e:
            logger.error(f"Router Bridge call failed: {e}")
            raise
        finally:
            sock.close()


# Singleton instance
_client: Optional[RouterBridgeClient] = None


def get_client() -> RouterBridgeClient:
    """Get or create singleton Router Bridge client instance."""
    global _client
    if _client is None:
        _client = RouterBridgeClient()
    return _client


def call(function_name: str, *args: Any, timeout: float = 5.0) -> Optional[Any]:
    """Convenience function to call Router Bridge function.

    Args:
        function_name: Name of the function to call
        *args: Arguments to pass to the function
        timeout: Timeout in seconds

    Returns:
        Function return value, or None if function returns void
    """
    return get_client().call(function_name, *args, timeout=timeout)
