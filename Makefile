.PHONY: install dev test lint typecheck format migrate backtest-demo paper-demo docker-up docker-down

install:
	pip install -r requirements.txt
	cd apps/web && npm install

dev:
	python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000 &
	cd apps/web && npm run dev

test:
	pytest tests -v

lint:
	ruff check .

typecheck:
	mypy apps/ services/ packages/

format:
	ruff format .

migrate:
	alembic upgrade head

backtest-demo:
	python scripts/run_backtest_demo.py

paper-demo:
	python scripts/run_paper_demo.py

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
