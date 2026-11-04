all:
	docker build -t hqg-backtester .
	docker build -f Dockerfile.sandbox -t hqg-backtester-sandbox .

deploy:
	uvicorn src.api.server:app --host 0.0.0.0 --port 8005

test:
	pytest -v tests/test_execution.py
