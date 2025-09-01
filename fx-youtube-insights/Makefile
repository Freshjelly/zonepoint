.PHONY: help install run snapshot rollup discord dashboard test clean

# Default target
help: ## Show this help message
	@echo "FX YouTube Analytics - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Dependencies installed!"

setup: ## Setup project (install + create directories)
	@echo "Setting up project..."
	make install
	mkdir -p data logs
	@echo "Project setup complete!"

run: setup ## Run Streamlit dashboard
	@echo "Starting FX YouTube Analytics Dashboard..."
	@echo "Access at: http://localhost:8501"
	streamlit run app/streamlit_app.py

snapshot: ## Run data collection snapshot
	@echo "Running data collection snapshot..."
	python scripts/run_snapshot.py

rollup: ## Run weekly metrics calculation
	@echo "Running weekly rollup calculation..."
	python scripts/run_rollup.py

discord: ## Send Discord weekly digest
	@echo "Sending Discord weekly digest..."
	python scripts/post_weekly_digest.py

discord-test: ## Test Discord webhook connection
	@echo "Testing Discord webhook..."
	python scripts/post_weekly_digest.py --test

full-pipeline: ## Run complete pipeline (snapshot -> rollup -> discord)
	@echo "Running complete pipeline..."
	make snapshot
	make rollup
	make discord

dashboard: run ## Alias for 'run'

test: ## Run basic functionality tests
	@echo "Running basic tests..."
	@echo "1. Testing database connection..."
	python -c "from etl.schema import DatabaseManager; db = DatabaseManager(); db.initialize_schema(); print('✓ Database OK')"
	@echo "2. Testing YouTube client..."
	python -c "from etl.youtube_client import YouTubeClient; yt = YouTubeClient(); status = yt.check_quota_status(); print(f'✓ YouTube API: {status[\"message\"]}')"
	@echo "3. Testing Discord webhook (if configured)..."
	python scripts/post_weekly_digest.py --test || echo "⚠ Discord webhook not configured"
	@echo "All tests completed!"

clean: ## Clean up logs and temporary files
	@echo "Cleaning up..."
	rm -rf logs/*.log
	rm -rf __pycache__/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleanup complete!"

reset-db: ## Reset database (WARNING: This will delete all data)
	@echo "WARNING: This will delete all collected data!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	rm -f data/analytics.duckdb
	@echo "Database reset complete!"

dev-setup: ## Development setup with dummy data
	@echo "Setting up development environment..."
	make setup
	@echo "Creating dummy data for development..."
	python -c "from etl.schema import DatabaseManager; db = DatabaseManager(); db.initialize_schema(); db.insert_dummy_data(); print('✓ Dummy data created')"
	python -c "from etl.rollup import WeeklyRollup; rollup = WeeklyRollup(); rollup.calculate_weekly_metrics(); print('✓ Weekly metrics calculated')"
	@echo "Development setup complete! Run 'make run' to see the dashboard."

status: ## Show project status
	@echo "FX YouTube Analytics - Project Status"
	@echo "======================================"
	@echo "📁 Project Structure:"
	@[ -f "requirements.txt" ] && echo "  ✓ requirements.txt" || echo "  ✗ requirements.txt"
	@[ -f ".env" ] && echo "  ✓ .env (configured)" || echo "  ⚠ .env (copy from .env.example and configure)"
	@[ -f "config/app.yaml" ] && echo "  ✓ config/app.yaml" || echo "  ✗ config/app.yaml"
	@[ -f "data/analytics.duckdb" ] && echo "  ✓ data/analytics.duckdb" || echo "  ⚠ data/analytics.duckdb (run 'make snapshot' or 'make dev-setup')"
	@echo ""
	@echo "🔧 Environment:"
	@python --version 2>/dev/null && echo "  ✓ Python available" || echo "  ✗ Python not found"
	@echo ""
	@echo "🚀 Quick Start:"
	@echo "  1. Copy .env.example to .env and configure API keys"
	@echo "  2. Run 'make dev-setup' for development with dummy data"
	@echo "  3. Run 'make run' to start the dashboard"