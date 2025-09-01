app-dir = bot

.PHONY: generate
generate:
	uv run alembic revision --m="$(NAME)" --autogenerate


.PHONY: migrate
migrate:
	uv run alembic upgrade head


.PHONY: build
build:
	uv run -m bot


.PHONY: sync_models
sync_models:
	cp ../post_manager/bot/db/models.py ../post_catcher/bot/db/models.py


.PHONY: format
format:
	echo "Running ruff check with --fix..."
	uv run ruff check --config pyproject.toml --fix --unsafe-fixes $(app-dir)

	echo "Running ruff..."
	uv run ruff format --config pyproject.toml $(app-dir)

	echo "Running isort..."
	uv run isort --settings-file pyproject.toml $(app-dir)
