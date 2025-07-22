.PHONY: lint format check test ci security

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