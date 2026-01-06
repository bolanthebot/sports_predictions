from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.nba import get_today_games,get_team,get_player,get_all_games,get_team_players
import json
from predict import predict_game
from predict_player import predict_player_points
import pandas as pd
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

#Gets teams active players ID's in list form http://localhost:8000/api/nba/teamplayers/?teamid=1610612761
@app.get("/api/nba/teamplayers/")
def get_active_players(teamid):
    players = get_team_players(teamid)
    pid = players["PLAYER_ID"].tolist()
    return pid

#gets player past games data by id eg http://localhost:8000/api/nba/players/?id=201935
@app.get("/api/nba/players/")
def player_games(id):
    return get_player(id).to_json(orient='records')

#http://localhost:8000/api/nba/predictions/today/?gameid=0022500423&teamid=1610612737
@app.get("/api/nba/predictions/today/")
def predictions(gameid: str, teamid: str):
    result = predict_game(gameid, teamid)
    return result

#Returns number of points exspected to be scored by a player
#http://localhost:8000/api/nba/predictions/player/today/?playerid=1629029
@app.get("/api/nba/predictions/player/today/")
def predictions(playerid: str):
    result = predict_player_points(playerid)
    print(result)
    return float(result["predicted_points"])
