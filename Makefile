.PHONY: up test-cache benchmark benchmark-warm benchmark-cold down clean \
	demo logs lb-lc lb-lrt benchmark-phase3

COMPOSE := docker compose
BENCHMARK_DURATION ?= 5
BENCHMARK_RATES ?= 10,40,70,100,130
BENCHMARK_FILE ?= twilight-annette-lyster.txt
BENCHMARK_KEYWORD ?= Christie

# Phase 3 benchmark settings
P3_RATES ?= 10,20,30,40,50
P3_DURATION ?= 10
P3_FILE ?= shakespeare.txt
P3_KEYWORD ?= love
SLOW := -f compose.yaml -f compose.slow.yaml
comma := ,

up:
	$(COMPOSE) build
	$(COMPOSE) up -d --wait redis server1 server2 server3 loadbalancer

test-cache: up
	$(COMPOSE) exec -T redis redis-cli FLUSHALL
	@echo "--- first request (expected cached=False) ---"
	$(COMPOSE) run --rm --no-deps client
	@echo "--- repeated request (expected cached=True) ---"
	$(COMPOSE) run --rm --no-deps client

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

demo: up
	$(COMPOSE) run --rm --no-deps client

logs:
	$(COMPOSE) logs -f loadbalancer server1 server2 server3

lb-lc:
	LB_ALGORITHM=least_connections $(COMPOSE) up -d --force-recreate --no-deps --wait loadbalancer

lb-lrt:
	LB_ALGORITHM=least_response_time $(COMPOSE) up -d --force-recreate --no-deps --wait loadbalancer

# $(1)=label, $(2)=port, $(3)=comma-separated compose files, $(4)=modes.
define p3_bench
for mode in $(4); do \
	uv run python scripts/benchmark.py --label $(1) --port $(2) \
		--compose-files "$(3)" --mode $$mode \
		--file "$(P3_FILE)" --keyword "$(P3_KEYWORD)" \
		--rates "$(P3_RATES)" --duration "$(P3_DURATION)" || exit 1; \
done
endef

# $(1)=label, $(2)=algorithm, $(3)=compose -f options, $(4)=compose files, $(5)=modes.
# The load balancer is recreated quietly (no per-connection log lines) first.
define p3_lb_bench
LB_ALGORITHM=$(2) LB_LOG_CONNECTIONS=0 $(COMPOSE) $(3) up -d --force-recreate --no-deps --wait loadbalancer
$(call p3_bench,$(1),18812,$(4),$(5))
endef

benchmark-phase3: up
	$(call p3_bench,phase3_single,18813,compose.yaml,warm cold)
	$(call p3_lb_bench,phase3_lc,least_connections,-f compose.yaml,compose.yaml,warm cold)
	$(call p3_lb_bench,phase3_lrt,least_response_time,-f compose.yaml,compose.yaml,warm cold)
	$(COMPOSE) $(SLOW) up -d --wait server3
	$(call p3_lb_bench,phase3_slow_lc,least_connections,$(SLOW),compose.yaml$(comma)compose.slow.yaml,cold)
	$(call p3_lb_bench,phase3_slow_lrt,least_response_time,$(SLOW),compose.yaml$(comma)compose.slow.yaml,cold)
	$(COMPOSE) up -d --force-recreate --wait server3 loadbalancer

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down --rmi local --volumes
