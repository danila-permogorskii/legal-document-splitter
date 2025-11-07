.PHONY: build run stop clean test dev logs

# Build Docker image
build:
	docker-compose build

# Run container
run:
	docker-compose up -d

# Stop container
stop:
	docker-compose down

# Clean everything
clean:
	docker-compose down -v
	rm -rf /tmp/jobs/*

# View logs
logs:
	docker-compose logs -f

# Development mode
dev:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Test health
test:
	curl http://localhost:8000/health
