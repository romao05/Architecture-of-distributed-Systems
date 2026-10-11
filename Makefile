.PHONY: up test-cache benchmark benchmark-warm benchmark-cold down clean

COMPOSE := docker compose
BENCHMARK_DURATION ?= 5
BENCHMARK_RATES ?= 10,40,70,100,130
BENCHMARK_FILE ?= twilight-annette-lyster.txt
BENCHMARK_KEYWORD ?= Christie

up:
	$(COMPOSE) build client server
	$(COMPOSE) up -d redis server

test-cache: up
	$(COMPOSE) exec -T redis redis-cli FLUSHALL
	@echo "--- first request (expected cached=False) ---"
	$(COMPOSE) run --rm client
	@echo "--- repeated request (expected cached=True) ---"
	$(COMPOSE) run --rm client

benchmark: benchmark-warm benchmark-cold

benchmark-warm: up
	uv run python scripts/benchmark.py \
		--file "$(BENCHMARK_FILE)" \
		--keyword "$(BENCHMARK_KEYWORD)" \
		--rates "$(BENCHMARK_RATES)" \
		--duration "$(BENCHMARK_DURATION)" \
		--mode warm

benchmark-cold: up
	uv run python scripts/benchmark.py \
		--file "$(BENCHMARK_FILE)" \
		--keyword "$(BENCHMARK_KEYWORD)" \
		--rates "$(BENCHMARK_RATES)" \
		--duration "$(BENCHMARK_DURATION)" \
		--mode cold

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down --rmi local --volumes
