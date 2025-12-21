from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.nba import get_today_games

app = FastAPI()

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/nba/games/today")
def today_games():
    return get_today_games()
