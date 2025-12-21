from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.nba import get_today_games
from services.nba import get_team

app = FastAPI()

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
#gets todays games returns json
@app.get("/api/nba/games/today")
def today_games():
    return get_today_games()

#gets team data by id eg http://localhost:8000/api/nba/teams/?id=1610612739
#return json
@app.get("/api/nba/teams/")
def team_data(id):
    return get_team(id)