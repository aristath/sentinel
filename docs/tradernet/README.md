# Tradernet API Documentation

This directory contains the complete Tradernet API documentation scraped from https://tradernet.com/tradernet-api/

## Documentation Structure

The documentation is organized into the following categories:

### Authentication

- [Auth Login](./authentication/auth-login.md)
- [Auth Api](./authentication/auth-api.md)
- [Auth Get Opq](./authentication/auth-get-opq.md)
- [Auth Get Sidinfo](./authentication/auth-get-sidinfo.md)
- [Public Api Client](./authentication/public-api-client.md)
- [Python Sdk](./authentication/python-sdk.md)

### Security Sessions

- [Security Get List](./security_sessions/security-get-list.md)
- [Open Security Session](./security_sessions/open-security-session.md)

### Securities Management

- [Quotes Get Lists](./securities_management/quotes-get-lists.md)
- [Quotes Add List](./securities_management/quotes-add-list.md)
- [Quotes Update List](./securities_management/quotes-update-list.md)
- [Quotes Delete List](./securities_management/quotes-delete-list.md)
- [Quotes Make List Selected](./securities_management/quotes-make-list-selected.md)
- [Quotes Add List Ticker](./securities_management/quotes-add-list-ticker.md)
- [Quotes Delete List Ticker](./securities_management/quotes-delete-list-ticker.md)

### Quotes & Market Data

- [Market Status](./quotes_and_market_data/market-status.md)
- [Quotes Get Info](./quotes_and_market_data/quotes-get-info.md)
- [Get Options By Mkt](./quotes_and_market_data/get-options-by-mkt.md)
- [Quotes Get Top Securities](./quotes_and_market_data/quotes-get-top-securities.md)
- [Quotes Get Changes](./quotes_and_market_data/quotes-get-changes.md)
- [Quotes Get](./quotes_and_market_data/quotes-get.md)
- [Quotes Orderbook](./quotes_and_market_data/quotes-orderbook.md)
- [Quotes Get Hloc](./quotes_and_market_data/quotes-get-hloc.md)
- [Get Trades](./quotes_and_market_data/get-trades.md)
- [Get Trades History](./quotes_and_market_data/get-trades-history.md)
- [Quotes Finder](./quotes_and_market_data/quotes-finder.md)
- [Quotes Get News](./quotes_and_market_data/quotes-get-news.md)
- [Securities](./quotes_and_market_data/securities.md)
- [Check Allowed Ticker And Ban On Trade](./quotes_and_market_data/check-allowed-ticker-and-ban-on-trade.md)

### Portfolio & Orders

- [Portfolio Get Changes](./portfolio_and_orders/portfolio-get-changes.md)
- [Orders Get Current History](./portfolio_and_orders/orders-get-current-history.md)
- [Get Orders History](./portfolio_and_orders/get-orders-history.md)
- [Orders Send](./portfolio_and_orders/orders-send.md)
- [Stop Loss](./portfolio_and_orders/stop-loss.md)
- [Orders Delete](./portfolio_and_orders/orders-delete.md)

### Alerts & Requests

- [Alerts Get List](./alerts_and_requests/alerts-get-list.md)
- [Alerts Add](./alerts_and_requests/alerts-add.md)
- [Alerts Delete](./alerts_and_requests/alerts-delete.md)
- [Get Client Cps History](./alerts_and_requests/get-client-cps-history.md)
- [Get Cps Files](./alerts_and_requests/get-cps-files.md)

### Reports

- [Broker Report](./reports/broker-report.md)
- [Broker Report Url](./reports/broker-report-url.md)
- [Depositary Report](./reports/depositary-report.md)
- [Broker Depositary Report Url](./reports/broker-depositary-report-url.md)
- [Get Cashflows](./reports/get-cashflows.md)

### Currencies & WebSocket

- [Cross Rates For Date](./currencies_and_websocket/cross-rates-for-date.md)
- [Currency](./currencies_and_websocket/currency.md)
- [Websocket](./currencies_and_websocket/websocket.md)
- [Websocket Sessions](./currencies_and_websocket/websocket-sessions.md)
- [Websocket Portfolio](./currencies_and_websocket/websocket-portfolio.md)
- [Websocket Orders](./currencies_and_websocket/websocket-orders.md)
- [Websocket Markets](./currencies_and_websocket/websocket-markets.md)

### Miscellaneous

- [Reception Types](./miscellaneous/reception-types.md)
- [Special Files List](./miscellaneous/special-files-list.md)
- [Mkt](./miscellaneous/mkt.md)
- [Instruments](./miscellaneous/instruments.md)
- [Cps Types List](./miscellaneous/cps-types-list.md)
- [Anketa Fields](./miscellaneous/anketa-fields.md)
- [Passport Type](./miscellaneous/passport-type.md)
- [Order Statuses](./miscellaneous/order-statuses.md)
- [Safety](./miscellaneous/safety.md)
- [Type Codes](./miscellaneous/type-codes.md)

## Scraping

The documentation was scraped using the script at `scripts/scrape_tradernet_docs.go`.

To re-scrape the documentation:

```bash
cd scripts
go run scrape_tradernet_docs.go
```

## Source

All documentation content is copyright Tradernet and sourced from their official API documentation website.

Last updated: 2026-01-09 11:23:00
