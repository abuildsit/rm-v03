.PHONY: lint format check test

# Run all linting and formatting
lint:
	poetry run black . && poetry run isort . --profile black && poetry run flake8 . --max-line-length=88 --extend-ignore=E203,W503 && poetry run mypy .

# Format code only
format:
	poetry run black .
	poetry run isort . --profile black

# Type check only
check:
	poetry run mypy .

# Run tests
test:
	poetry run pytest