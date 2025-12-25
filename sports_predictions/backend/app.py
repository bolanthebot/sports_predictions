from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.nba import get_today_games,get_team,get_player
import json
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

#gets team past games data by id eg http://localhost:8000/api/nba/teams/?id=1610612739
#return json
@app.get("/api/nba/teams/")
def team_games(id):
    return get_team(id).to_json(orient='records')

#gets player past games data by id eg http://localhost:8000/api/nba/players/?id=201935
@app.get("/api/nba/players/")
def player_games(id):
    return get_player(id).to_json(orient='records')