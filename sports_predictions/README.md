For jsx dependencies run:
`npm install`

For python depenencies run:
`pip install pandas numpy scikit-learn nba_api FastAPI xgboost`

Run backend from `/sports_predictions/backend`:
`py -m uvicorn app:app --reload --host 0.0.0.0 --port 8000`

Run frontend from `/sports_predictions`:
`npm run dev`

Once both are running open http://localhost:5173/ in browser.
