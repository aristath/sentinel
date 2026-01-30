"""Entry point for `python -m sentinel_tui`."""

from sentinel_tui.config import get_api_url


def main() -> None:
    api_url = get_api_url()

    # Import app after config so argparse runs first
    from sentinel_tui.app import SentinelApp

    app = SentinelApp(api_url=api_url)
    app.run()


if __name__ == "__main__":
    main()
