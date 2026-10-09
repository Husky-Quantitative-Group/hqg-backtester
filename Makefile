all:
	docker build -t hqg-backtester .
	docker build -t hqg-backtester-sandbox .

test:
	pytest -v tests/test_execution.py
