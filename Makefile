# ===== Config =====
CORE_DIR := core
CONTROL_DIR := control
CORE_BIN := $(CORE_DIR)/target/release/core

FEATURE ?= RBAC

# ===== Help =====
.PHONY: help
help:
	@echo "Available commands:"
	@echo "  make build        - Build Rust core (release)"
	@echo "  make run          - Run MCP control server"
	@echo "  make full         - Run full intent (FEATURE=$(FEATURE))"
	@echo "  make approve      - Approve feature (FEATURE=$(FEATURE))"
	@echo "  make clean        - Clean Rust build artifacts"

# ===== Build Rust core =====
.PHONY: build
build:
	cd $(CORE_DIR) && cargo build --release

.PHONY: core
core:
	cd $(CORE_DIR) && cargo build --release

# ===== Run MCP Server =====
.PHONY: run
run: core
	cd $(CONTROL_DIR) && uv run python server.py

# ===== Intent helpers =====
.PHONY: full
full:
	echo '{"method":"full","params":{"feature":"$(FEATURE)"}}' \
	| cd $(CONTROL_DIR) && uv run python server.py

.PHONY: approve
approve:
	echo '{"method":"approve","params":{"feature":"$(FEATURE)"}}' \
	| cd $(CONTROL_DIR) && uv run python server.py

# ===== Clean =====
.PHONY: clean
clean:
	cd $(CORE_DIR) && cargo clean
