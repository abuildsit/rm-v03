.PHONY: lint format check test ci security dev keep-log

# Run all linting and formatting
lint:
	poetry run black . && poetry run isort . --profile black && poetry run flake8 . --max-line-length=88 --extend-ignore=E203,W503 --exclude=prisma/,workflow-documentation/ && poetry run mypy src/
# Format code only
format:
	poetry run black .
	poetry run isort . --profile black

# Type check only
check:
	poetry run mypy src/

# Run tests
test:
	poetry run pytest

# Security scanning
security:
	poetry run bandit -r src/ -f json || echo "⚠️  Security issues found - review bandit output"

# Run full CI pipeline: generate schema, lint, test
ci:
	poetry run prisma generate && $(MAKE) lint && $(MAKE) test

# Run development server in new terminal
dev:
	@if echo "$(MAKECMDGOALS)" | grep -q "keep-log"; then \
		echo "Keeping existing server.log"; \
		gnome-terminal -- bash -c "poetry run uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload 2>&1 | while IFS= read -r line; do echo \"\$$(date '+%Y-%m-%d %H:%M:%S') \$$line\"; done | tee -a server.log; exec bash"; \
	else \
		echo "Clearing server.log"; \
		> server.log; \
		gnome-terminal -- bash -c "poetry run uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload 2>&1 | while IFS= read -r line; do echo \"\$$(date '+%Y-%m-%d %H:%M:%S') \$$line\"; done | tee server.log; exec bash"; \
	fi

# Dummy target for keep-log argument
keep-log:
	@: