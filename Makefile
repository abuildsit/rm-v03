.PHONY: help lint format check test ci security dev lint-api format-api check-api test-api ci-api security-api dev-api lint-web format-web check-web test-web ci-web security-web dev-web

# Default target
help:
	@echo "Root Makefile for RM-V03 Project"
	@echo ""
	@echo "Project-wide commands:"
	@echo "  make lint      - Run linting for all apps"
	@echo "  make format    - Run formatting for all apps"
	@echo "  make check     - Run type checking for all apps"
	@echo "  make test      - Run tests for all apps"
	@echo "  make ci        - Run full CI pipeline for all apps"
	@echo "  make security  - Run security scanning for all apps"
	@echo "  make dev       - Start development servers for all apps"
	@echo ""
	@echo "API-specific commands:"
	@echo "  make lint-api      - Run API linting"
	@echo "  make format-api    - Run API formatting"
	@echo "  make check-api     - Run API type checking"
	@echo "  make test-api      - Run API tests"
	@echo "  make ci-api        - Run API CI pipeline"
	@echo "  make security-api  - Run API security scanning"
	@echo "  make dev-api       - Start API development server"
	@echo ""
	@echo "Web-specific commands:"
	@echo "  make lint-web      - Run web linting"
	@echo "  make format-web    - Run web formatting"
	@echo "  make check-web     - Run web type checking"
	@echo "  make test-web      - Run web tests"
	@echo "  make ci-web        - Run web CI pipeline"
	@echo "  make security-web  - Run web security scanning"
	@echo "  make dev-web       - Start web development server"

# ============================================================================
# PROJECT-WIDE COMMANDS (run for all apps)
# ============================================================================

lint: lint-api lint-web
	@echo "✅ Linting completed for all apps"

format: format-api format-web
	@echo "✅ Formatting completed for all apps"

check: check-api check-web
	@echo "✅ Type checking completed for all apps"

test: test-api test-web
	@echo "✅ Testing completed for all apps"

ci: ci-api ci-web
	@echo "✅ CI pipeline completed for all apps"

security: security-api security-web
	@echo "✅ Security scanning completed for all apps"

dev:
	@echo "🚀 Starting development servers for all apps..."
	@$(MAKE) dev-api &
	@$(MAKE) dev-web &
	@echo "✅ Development servers started"

# ============================================================================
# API-SPECIFIC COMMANDS
# ============================================================================

lint-api:
	@echo "🔍 Running API linting..."
	@cd apps/api && $(MAKE) lint

format-api:
	@echo "🎨 Running API formatting..."
	@cd apps/api && $(MAKE) format

check-api:
	@echo "🔎 Running API type checking..."
	@cd apps/api && $(MAKE) check

test-api:
	@echo "🧪 Running API tests..."
	@cd apps/api && $(MAKE) test

ci-api:
	@echo "🏗️ Running API CI pipeline..."
	@cd apps/api && $(MAKE) ci

security-api:
	@echo "🔒 Running API security scanning..."
	@cd apps/api && $(MAKE) security

dev-api:
	@echo "🚀 Starting API development server..."
	@cd apps/api && $(MAKE) dev

dev-api-keep-log:
	@echo "🚀 Starting API development server (keeping logs)..."
	@cd apps/api && $(MAKE) dev keep-log

# ============================================================================
# WEB-SPECIFIC COMMANDS
# ============================================================================

lint-web:
	@echo "🔍 Running web linting..."
	@if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then \
		cd apps/web && npm run lint; \
	else \
		echo "⚠️  Web app not found or no package.json - skipping web linting"; \
	fi

format-web:
	@echo "🎨 Running web formatting..."
	@if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then \
		cd apps/web && npm run format; \
	else \
		echo "⚠️  Web app not found or no package.json - skipping web formatting"; \
	fi

check-web:
	@echo "🔎 Running web type checking..."
	@if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then \
		cd apps/web && npm run type-check; \
	else \
		echo "⚠️  Web app not found or no package.json - skipping web type checking"; \
	fi

test-web:
	@echo "🧪 Running web tests..."
	@if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then \
		cd apps/web && npm test; \
	else \
		echo "⚠️  Web app not found or no package.json - skipping web tests"; \
	fi

ci-web:
	@echo "🏗️ Running web CI pipeline..."
	@if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then \
		cd apps/web && npm run ci; \
	else \
		echo "⚠️  Web app not found or no package.json - skipping web CI"; \
	fi

security-web:
	@echo "🔒 Running web security scanning..."
	@if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then \
		cd apps/web && npm audit; \
	else \
		echo "⚠️  Web app not found or no package.json - skipping web security scanning"; \
	fi

dev-web:
	@echo "🚀 Starting web development server..."
	@if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then \
		cd apps/web && npm run dev; \
	else \
		echo "⚠️  Web app not found or no package.json - skipping web development server"; \
	fi

# ============================================================================
# UTILITY COMMANDS
# ============================================================================

clean:
	@echo "🧹 Cleaning all build artifacts..."
	@cd apps/api && rm -rf __pycache__ .pytest_cache .mypy_cache
	@if [ -d "apps/web" ]; then \
		cd apps/web && rm -rf node_modules dist .next build; \
	fi
	@echo "✅ Cleanup completed"

install:
	@echo "📦 Installing dependencies for all apps..."
	@echo "Installing API dependencies..."
	@cd apps/api && poetry install
	@if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then \
		echo "Installing web dependencies..."; \
		cd apps/web && npm install; \
	else \
		echo "⚠️  Web app not found - skipping web dependencies"; \
	fi
	@echo "✅ Dependencies installed for all apps"

status:
	@echo "📊 Project Status"
	@echo "================"
	@echo "API Status:"
	@if [ -f "apps/api/pyproject.toml" ]; then \
		echo "  ✅ API project found"; \
		cd apps/api && poetry --version; \
	else \
		echo "  ❌ API project not found"; \
	fi
	@echo ""
	@echo "Web Status:"
	@if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then \
		echo "  ✅ Web project found"; \
		cd apps/web && node --version && npm --version; \
	else \
		echo "  ❌ Web project not found or incomplete"; \
	fi