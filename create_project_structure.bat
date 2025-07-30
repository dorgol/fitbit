@echo off
echo Creating Fitbit AI POC project structure...

REM Create main directories
mkdir src
mkdir src\core
mkdir src\memory
mkdir src\agents
mkdir src\utils
mkdir src\api
mkdir notebooks
mkdir tests
mkdir data
mkdir sql
mkdir docs

REM Create __init__.py files for Python packages
echo. > src\__init__.py
echo. > src\core\__init__.py
echo. > src\memory\__init__.py
echo. > src\agents\__init__.py
echo. > src\utils\__init__.py
echo. > src\api\__init__.py
echo. > tests\__init__.py

REM Create main Python files
echo # Entry point for POC demo > src\main.py
echo # Conversation orchestrator > src\core\conversation_orchestrator.py
echo # Context assembly > src\core\context_assembly.py
echo # Response generator > src\core\response_generator.py

echo # Database connection and models > src\memory\database.py
echo # Raw data layer > src\memory\raw_data.py
echo # Insights generation > src\memory\insights.py
echo # Conversation highlights > src\memory\highlights.py
echo # External data (weather, etc.) > src\memory\external_data.py
echo # Knowledge base > src\memory\knowledge.py

echo # Main conversation agent > src\agents\health_assistant.py
echo # LangGraph workflow definitions > src\agents\workflows.py

echo # Mock data generation > src\utils\mock_data.py
echo # Configuration management > src\utils\config.py
echo # Logging setup > src\utils\logging.py

echo # Claude API wrapper > src\api\claude_client.py
echo # Weather API client > src\api\weather_client.py

REM Create test files
echo # Test conversation functionality > tests\test_conversation.py
echo # Test memory system > tests\test_memory.py
echo # Test insights generation > tests\test_insights.py

REM Create data files
echo {} > data\mock_health_data.json
echo {} > data\knowledge_base.json

REM Create requirements.txt
(
echo # Core framework
echo langgraph^>=0.0.40
echo langchain^>=0.1.0
echo anthropic^>=0.7.0
echo.
echo # Database
echo psycopg2-binary^>=2.9.0
echo sqlalchemy^>=2.0.0
echo alembic^>=1.12.0
echo.
echo # Data processing
echo pandas^>=2.0.0
echo numpy^>=1.24.0
echo.
echo # API clients
echo requests^>=2.31.0
echo python-dotenv^>=1.0.0
echo.
echo # Development
echo jupyter^>=1.0.0
echo pytest^>=7.4.0
echo black^>=23.0.0
echo flake8^>=6.0.0
) > requirements.txt

REM Create .env.example
(
echo # API Keys
echo ANTHROPIC_API_KEY=your_claude_api_key_here
echo WEATHER_API_KEY=your_weather_api_key_here
echo.
echo # Database
echo DATABASE_URL=postgresql://localhost:5432/fitbit_ai_poc
echo DATABASE_USER=fitbit_user
echo DATABASE_PASSWORD=fitbit_password
echo DATABASE_NAME=fitbit_ai_poc
echo.
echo # Application settings
echo DEBUG=True
echo LOG_LEVEL=INFO
echo CONVERSATION_HISTORY_LIMIT=3
echo.
echo # External services
echo WEATHER_BASE_URL=https://api.openweathermap.org/data/2.5
echo DEFAULT_LOCATION=Tel Aviv,IL
) > .env.example

REM Create .gitignore
(
echo # Environment
echo .env
echo .venv/
echo venv/
echo env/
echo.
echo # Python
echo __pycache__/
echo *.pyc
echo *.pyo
echo *.pyd
echo .Python
echo *.so
echo .pytest_cache/
echo.
echo # Jupyter
echo .ipynb_checkpoints/
echo *.ipynb_checkpoints
echo.
echo # Database
echo *.db
echo *.sqlite3
echo.
echo # IDE
echo .vscode/
echo .idea/
echo *.swp
echo *.swo
echo.
echo # OS
echo .DS_Store
echo Thumbs.db
echo.
echo # Logs
echo *.log
echo logs/
echo.
echo # Data
echo data/local_*
) > .gitignore

REM Create README.md
(
echo # Fitbit AI POC
echo.
echo Conversational AI assistant for personalized health insights.
echo.
echo ## Setup
echo ```
echo python -m venv venv
echo venv\Scripts\activate
echo pip install -r requirements.txt
echo copy .env.example .env
echo ^(edit .env with your API keys^)
echo ```
echo.
echo ## Run
echo ```
echo python src\main.py
echo ```
) > README.md

REM Create setup.py
(
echo from setuptools import setup, find_packages
echo.
echo setup^(
echo     name="fitbit-ai-poc",
echo     version="0.1.0",
echo     description="Fitbit Conversational AI Proof of Concept",
echo     packages=find_packages^(where="src"^),
echo     package_dir={"": "src"},
echo     python_requires="^>=3.9",
echo     install_requires=[
echo         "langgraph^>=0.0.40",
echo         "langchain^>=0.1.0",
echo         "anthropic^>=0.7.0",
echo         "psycopg2-binary^>=2.9.0",
echo         "sqlalchemy^>=2.0.0",
echo         "pandas^>=2.0.0",
echo         "requests^>=2.31.0",
echo         "python-dotenv^>=1.0.0",
echo     ],
echo ^)
) > setup.py

REM Create basic SQL schema
(
echo -- Users table
echo CREATE TABLE users ^(
echo     id SERIAL PRIMARY KEY,
echo     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
echo     age INTEGER,
echo     gender VARCHAR^(10^),
echo     location VARCHAR^(100^),
echo     goals JSONB,
echo     preferences JSONB
echo ^);
echo.
echo -- Health metrics table
echo CREATE TABLE health_metrics ^(
echo     id SERIAL PRIMARY KEY,
echo     user_id INTEGER REFERENCES users^(id^),
echo     metric_type VARCHAR^(50^),
echo     value FLOAT,
echo     timestamp TIMESTAMP,
echo     metadata JSONB
echo ^);
echo.
echo CREATE INDEX idx_health_metrics_user_time ON health_metrics^(user_id, timestamp DESC^);
) > sql\schema.sql

echo.
echo Project structure created successfully!
echo.
echo Next steps:
echo 1. python -m venv venv
echo 2. venv\Scripts\activate
echo 3. pip install -r requirements.txt
echo 4. copy .env.example .env
echo 5. Edit .env with your API keys
echo.
echo Ready to start coding!