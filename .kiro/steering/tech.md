# Technology Stack

## Framework & Runtime
- **FastAPI**: Modern Python web framework for building APIs
- **Python 3.11**: Runtime environment
- **Uvicorn**: ASGI server for development
- **Gunicorn**: Production WSGI server with Uvicorn workers

## Database & ORM
- **PostgreSQL**: Primary database with JSONB support for tags and metadata
- **SQLAlchemy 2.0+**: ORM with async support
- **Psycopg2**: PostgreSQL adapter
- **Alembic**: Database migrations

## Data Models & Validation
- **Pydantic 2.5+**: Data validation and serialization
- **Pydantic Settings**: Configuration management
- **Dataclasses**: Internal model definitions (Product, Ingredient)

## Performance & Monitoring
- **Redis**: Caching layer
- **psutil**: System performance monitoring
- **Custom TimeTracker**: Request timing and performance metrics

## Testing
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **pytest-cov**: Coverage reporting
- **pytest-xdist**: Parallel test execution

## Development & Deployment
- **Docker**: Containerization
- **Render**: Cloud deployment platform
- **Environment Variables**: Configuration via .env files

## Common Commands

### Development
```bash
# Start development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest

# Run tests with coverage
pytest --cov=app

# Install dependencies
pip install -r requirements.txt
```

### Production
```bash
# Start production server
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Docker build
docker build -t cosmetic-api .

# Docker run
docker run -p 8000:8000 cosmetic-api
```

### Database
```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```