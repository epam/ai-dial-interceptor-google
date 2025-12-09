# ============================================================
# Makefile for ai-dial-interceptor-google
# ============================================================

PYTHON      := python3
POETRY      := poetry
DOCKER      := docker
DC          := docker compose
PACKAGE     := ai_dial_interceptor_google
SRC_DIR     := src/ai_dial_interceptor_google
IMAGE       := ai-dial-interceptor-google
TAG         := latest

# Default target
.DEFAULT_GOAL := help

# ============================================================
# HELP
# ============================================================
.PHONY: help
help:
	@echo ""
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make lint           - Run flake8, isort, mypy"
	@echo "  make format         - Run black + isort formatting"
	@echo "  make test           - Run pytest"
	@echo "  make build          - Build Python package via Poetry"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make docker-run     - Start service in Docker locally"
	@echo "  make docker-stop    - Stop Docker service"
	@echo "  make publish        - Publish Python package to PyPI"
	@echo "  make docker-push    - Push Docker image to registry"
	@echo "  make clean          - Remove caches and build artifacts"
	@echo ""

# ============================================================
# INSTALL
# ============================================================
.PHONY: install
install:
	$(POETRY) lock
	@echo "Installing project..."
	$(POETRY) install --no-interaction

# ============================================================
# LINTING
# ============================================================
.PHONY: lint
lint:
	@echo "Running flake8..."
	$(POETRY) run flake8 $(SRC_DIR)

	@echo "Running isort..."
	$(POETRY) run isort --check-only $(SRC_DIR)

	@echo "Running mypy..."
	$(POETRY) run mypy $(SRC_DIR)

# ============================================================
# FORMATTING
# ============================================================
.PHONY: format
format:
	@echo "Running black formatter..."
	$(POETRY) run black $(SRC_DIR)
	@echo "Running isort formatter..."
	$(POETRY) run isort $(SRC_DIR)

# ============================================================
# TEST
# ============================================================
.PHONY: test
test:
	@echo "Running pytest..."
	$(POETRY) run pytest -q

# ============================================================
# BUILD PYTHON PACKAGE
# ============================================================
.PHONY: build
build:
	@echo "Building wheel and package..."
	$(POETRY) build

# ============================================================
# DOCKER
# ============================================================
.PHONY: docker-build
docker-build:
	@echo "Building Docker image $(IMAGE):$(TAG)..."
	$(DOCKER) build -t $(IMAGE):$(TAG) .

.PHONY: docker-run
docker-run:
	@echo "Starting Docker service..."
	$(DC) up -d

.PHONY: docker-stop
docker-stop:
	@echo "Stopping Docker service..."
	$(DC) down

# ============================================================
# PUBLISH PYTHON PACKAGE TO PYPI
# ============================================================
.PHONY: publish
publish:
	@echo "Publishing package to PyPI..."
	$(POETRY) publish --build

# ============================================================
# DOCKER PUBLISH
# ============================================================
.PHONY: docker-push
docker-push:
	@echo "Pushing Docker image..."
	$(DOCKER) push $(IMAGE):$(TAG)

# ============================================================
# CLEAN
# ============================================================
.PHONY: clean
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/ dist/ *.egg-info
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -exec rm -r {} +
	@echo "Done."
