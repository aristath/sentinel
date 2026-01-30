"""Sentinel TUI — main Textual application."""

from __future__ import annotations

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static

from sentinel_tui.api.client import SentinelAPI


class ConnectionStatus(Static):
    """Displays API connection status in the header bar."""

    def update_status(self, connected: bool, detail: str = "") -> None:
        if connected:
            self.update(f"[green]Connected[/] {detail}")
        else:
            self.update(f"[red]Disconnected[/] {detail}")


class PortfolioSummary(Static):
    """Panel showing portfolio totals."""

    DEFAULT_CSS = """
    PortfolioSummary {
        height: auto;
        padding: 0 1;
        border-bottom: solid $accent;
    }
    """

    def set_data(self, data: dict) -> None:
        total = data.get("total_value_eur", 0)
        cash_eur = data.get("total_cash_eur", 0)
        invested = total - cash_eur
        self.update(
            f"[bold]Total:[/] €{total:,.2f}  [bold]Invested:[/] €{invested:,.2f}  [bold]Cash:[/] €{cash_eur:,.2f}"
        )

    def set_error(self, msg: str) -> None:
        self.update(f"[red]{msg}[/]")


class SentinelApp(App):
    """Sentinel terminal UI."""

    TITLE = "Sentinel"
    CSS = """
    #status-bar {
        dock: top;
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    #securities-table {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, api_url: str) -> None:
        super().__init__()
        self.api = SentinelAPI(api_url)
        self.api_url = api_url

    def compose(self) -> ComposeResult:
        yield Header()
        yield ConnectionStatus(id="status-bar")
        yield PortfolioSummary()
        yield DataTable(id="securities-table")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#securities-table", DataTable)
        table.add_columns("Symbol", "Value (€)", "P/L (%)")
        await self._load_data()

    async def _load_data(self) -> None:
        status = self.query_one(ConnectionStatus)
        summary = self.query_one(PortfolioSummary)
        table = self.query_one("#securities-table", DataTable)

        # Health check
        try:
            health = await self.api.health()
            mode = health.get("trading_mode", "")
            status.update_status(True, f"({mode})" if mode else "")
        except Exception as exc:
            status.update_status(False, str(exc))
            summary.set_error(f"Cannot reach API at {self.api_url}")
            return

        # Portfolio
        try:
            portfolio = await self.api.portfolio()
            summary.set_data(portfolio)
        except Exception as exc:
            summary.set_error(str(exc))

        # Securities table (all universe, sorted by value desc)
        try:
            securities = await self.api.unified()
            securities.sort(key=lambda s: s.get("value_eur", 0) or 0, reverse=True)
            table.clear()
            for sec in securities:
                value = sec.get("value_eur", 0) or 0
                has_pos = sec.get("has_position", False)
                if has_pos:
                    value_text = f"{value:,.2f}"
                    pct = sec.get("profit_pct", 0) or 0
                    color = "green" if pct >= 0 else "red"
                    pl_text = Text(f"{pct:+.2f}%", style=color)
                else:
                    value_text = Text("-", style="dim")
                    pl_text = Text("-", style="dim")
                table.add_row(sec.get("symbol", ""), value_text, pl_text)
        except Exception as exc:
            self.log.error(f"Failed to load securities: {exc}")

    async def action_refresh(self) -> None:
        await self._load_data()

    async def on_unmount(self) -> None:
        await self.api.close()
