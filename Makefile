# Healthcare Revenue Cycle Command Center
# Usage: make <target>   (on Windows, use Git Bash or `make` from WSL;
# each target's underlying command also works directly.)

.PHONY: install pipeline validate automation load api frontend frontend-build db-up db-down all

install:            ## Install Python dependencies
	python -m pip install -r requirements.txt

pipeline:           ## Run the full ETL pipeline (generate + transform + export CSVs)
	python etl/run_pipeline.py

validate:           ## Run data quality validation
	python etl/validate_data.py

automation:         ## Run the follow-up task / alert rules engine
	python automation/generate_followup_tasks.py

load:               ## Load processed CSVs into PostgreSQL (requires db-up)
	python etl/load_to_postgres.py

api:                ## Start the FastAPI backend on :8000
	uvicorn api.main:app --reload --port 8000

frontend:           ## Start the React dev server on :5173
	cd frontend && npm run dev

frontend-build:     ## Production build of the frontend
	cd frontend && npm run build

db-up:              ## Start PostgreSQL via Docker Compose
	docker compose up -d

db-down:            ## Stop PostgreSQL
	docker compose down

all: install pipeline validate automation   ## Full local data build
