# Project E Python EV Scraper

This microservice scrapes electric vehicle rows from:
- `https://en.wikipedia.org/wiki/List_of_production_battery_electric_vehicles`

It exposes endpoints for backend integration:
- `GET /health`
- `POST /vehicles/scrape`
- `DELETE /vehicles/cache`

## Run

```bash
cd Back/Project_E.PythonScraper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Windows PowerShell:

```powershell
cd Back/Project_E.PythonScraper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```
