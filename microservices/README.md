# Microservices

This directory contains Python microservices that provide specialized functionality to the main Go trading application.

## Active Microservices

### pypfopt

A thin wrapper around the PyPortfolioOpt library for portfolio optimization.

- **Purpose:** Portfolio optimization using Mean-Variance, Black-Litterman, and other algorithms
- **Language:** Python
- **Why Python:** PyPortfolioOpt is a Python-native library with complex mathematical dependencies

### tradernet

A wrapper around the Tradernet SDK for broker integration.

- **Purpose:** Trading, position management, and data synchronization with Tradernet broker
- **Language:** Python
- **Why Python:** Tradernet provides a Python SDK

## Communication

These microservices communicate with the main Go application via HTTP/gRPC APIs.

## Future Microservices

Additional microservices may be added here as needed for specialized functionality that:
- Requires Python-specific libraries
- Benefits from language-specific tooling
- Provides isolated, independent functionality
