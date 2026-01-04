.PHONY: help build run test clean fmt lint deps

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

deps: ## Download dependencies
	go mod download
	go mod verify

build: ## Build the application
	@./scripts/build.sh

build-arm64: ## Build for ARM64 (Arduino Uno Q)
	@./scripts/build.sh arm64

run: ## Run the application
	go run ./cmd/server

dev: ## Run with auto-reload (requires air)
	air

test: ## Run tests
	go test -v -race -coverprofile=coverage.out ./...

test-coverage: test ## Run tests and show coverage
	go tool cover -html=coverage.out

fmt: ## Format code
	go fmt ./...
	gofmt -s -w .

lint: ## Run linter
	golangci-lint run

clean: ## Clean build artifacts
	rm -f trader-go trader-go-arm64 coverage.out
	go clean

docker-build: ## Build Docker image
	docker build -t arduino-trader:latest .

.DEFAULT_GOAL := help
