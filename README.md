# Real-Time Data Streaming Platform

A real-time data streaming platform that ingests cryptocurrency data from CoinGecko API, processes it, and displays live metrics on an interactive dashboard.

## Features

- **Real-time Data Ingestion**: Fetches live cryptocurrency market data from CoinGecko API
- **Data Transformation & Validation**: Cleans, validates, and aggregates incoming data
- **Live Dashboard**: Web-based dashboard showing real-time metrics and trends
- **CI/CD Pipeline**: Automated testing and deployment with GitHub Actions
- **Monitoring & Logging**: Comprehensive logging and error tracking

## Tech Stack

- **Backend**: Python 3.9+, Flask
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Data Source**: CoinGecko API (No authentication required)
- **Database**: SQLite (or in-memory for demo)
- **CI/CD**: GitHub Actions
- **Testing**: pytest, pytest-cov

## Project Structure

```
.
├── backend/
│   ├── app.py                 # Flask application
│   ├── data_ingestion.py      # CoinGecko API integration
│   ├── transformations.py     # Data cleaning & transformation
│   └── config.py              # Configuration
├── frontend/
│   ├── index.html             # Dashboard UI
│   ├── styles.css             # Dashboard styling
│   └── script.js              # Dashboard JavaScript
├── tests/
│   ├── test_ingestion.py      # Tests for data ingestion
│   ├── test_transformations.py # Tests for transformations
│   └── test_integration.py    # End-to-end tests
├── .github/workflows/
│   └── ci.yml                 # GitHub Actions CI/CD pipeline
├── requirements.txt           # Python dependencies
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## Getting Started

### Prerequisites
- Python 3.9 or higher
- pip or conda

### Installation

1. Clone the repository:
```bash
git clone https://github.com/nana-evansankomah/Agile-and-Devops-Lab.git
cd Agile-and-Devops-Lab
```

2. Create a virtual environment:
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python run.py
```

5. Open your browser and go to:
```
http://localhost:5000
```

## Running Tests

```bash
pytest tests/ -v --cov=backend
```

## CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment. Every push and pull request triggers:
- `quick-checks.yml`: fast lint + unit checks
- `integration-smoke.yml`: integration tests + startup smoke check
- `ci.yml`: full matrix tests + coverage + build smoke

See `.github/workflows/` for all pipeline configurations.

## Data Source

This project uses the **CoinGecko API** which provides:
- No authentication required
- Real-time cryptocurrency market data
- Free tier: 10-50 calls/minute
- Full API documentation: https://www.coingecko.com/en/api

## Sprint Organization

- **Sprint 0**: Planning & Product Backlog
- **Sprint 1**: Data Ingestion, Dashboard, CI/CD Setup
- **Sprint 2**: Data Quality Monitoring, Enhancements, Testing

See [Sprint0_Planning.md](Sprint0_Planning.md) for detailed backlog and sprint planning.

## License

This is an educational project for Agile and DevOps learning.
