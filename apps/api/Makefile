.PHONY: lint format check test

# Run all linting and formatting
lint:
	poetry run black . && poetry run isort . --profile black && poetry run flake8 . --max-line-length=88 --extend-ignore=E203,W503 --exclude=prisma/ && poetry run mypy src/
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