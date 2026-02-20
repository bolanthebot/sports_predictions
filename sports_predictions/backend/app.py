import os
import logging
import threading
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import List

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import asyncio

from services.nba import get_today_games, get_team, get_player, get_all_games, get_team_players
from services.injury import fetch_espn_injuries, TEAM_ID_TO_ABBR
from services.cache import cache_get
from predict import predict_game, predict_all_games, PREDICTION_CACHE_PATH
from predict_player import predict_player_points

# Load environment variables (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration from environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))

# CORS configuration
# Parse allowed origins from environment (comma-separated)
_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
ALLOWED_ORIGINS = [origin.strip() for origin in _origins_env.split(",") if origin.strip()]

# Azure App Service provides WEBSITE_HOSTNAME
AZURE_HOSTNAME = os.getenv("WEBSITE_HOSTNAME")
if AZURE_HOSTNAME:
    # Running on Azure - auto-detect production mode
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    logger_startup = logging.getLogger(__name__)
    logger_startup.info(f"Running on Azure: {AZURE_HOSTNAME}")

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Thread pool for running blocking prediction calls
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Warmup state — tracks whether game predictions have been pre-computed
_warmup_complete = threading.Event()
_warmup_error = None


def _run_warmup():
    """Pre-compute all game predictions so user requests never trigger heavy computation."""
    global _warmup_error
    try:
        logger.info("Warmup: pre-computing game predictions...")
        predict_all_games()
        logger.info("Warmup: game predictions cached successfully")
    except Exception as e:
        _warmup_error = str(e)
        logger.error(f"Warmup failed: {e}", exc_info=True)
    finally:
        _warmup_complete.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting Sports Predictions API ({ENVIRONMENT})")
    warmup_thread = threading.Thread(target=_run_warmup, daemon=True)
    warmup_thread.start()
    yield
    logger.info("Shutting down Sports Predictions API")
    _executor.shutdown(wait=True)


app = FastAPI(
    title="Sports Predictions API",
    description="NBA game and player predictions API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if ENVIRONMENT != "production" else None,  # Disable docs in production
    redoc_url="/redoc" if ENVIRONMENT != "production" else None,
)

# CORS configuration - use environment-based origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc) if ENVIRONMENT != "production" else None}
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": ENVIRONMENT
    }


# Readiness check - verifies dependencies are available
@app.get("/ready", tags=["Health"])
def readiness_check():
    """Readiness check - verifies the service can handle requests."""
    try:
        # Quick check that we can access NBA API
        from services.cache import get_cache_path
        import os
        cache_path = get_cache_path("nba_api_cache.pkl")
        cache_exists = os.path.exists(cache_path)
        
        return {
            "status": "ready",
            "cache_available": cache_exists,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")
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
    pid = [players["PLAYER_ID"].tolist(), players["PLAYER"].tolist()]
    return pid

#gets player past games data by id eg http://localhost:8000/api/nba/players/?id=201935
@app.get("/api/nba/players/")
def player_games(id):
    return get_player(id).to_json(orient='records')

#http://localhost:8000/api/nba/predictions/today/?gameid=0022500423&teamid=1610612737
@app.get("/api/nba/predictions/today/")
def predictions(gameid: str, teamid: str):
    # Fast path: check cache directly (instant if warmup already populated it)
    cache_key = f"predict_game:{date.today().isoformat()}:{gameid}:{teamid}"
    cached = cache_get(PREDICTION_CACHE_PATH, cache_key)
    if cached is not None:
        return cached

    # Cache miss — if warmup is still running, tell the client to retry
    # instead of triggering the slow computation on this request
    if not _warmup_complete.is_set():
        return {"status": "warming_up", "message": "Predictions are being generated. Please retry in a few seconds."}

    # Warmup finished but this specific game wasn't cached (edge case)
    result = predict_game(gameid, teamid)
    return result


@app.get("/api/nba/predictions/status")
def prediction_status():
    """Check if game predictions have been pre-computed and are ready to serve."""
    return {
        "ready": _warmup_complete.is_set(),
        "error": _warmup_error,
    }

#Returns number of points exspected to be scored by a player
#http://localhost:8000/api/nba/predictions/player/today/?playerid=1629029
@app.get("/api/nba/predictions/player/today/")
def player_prediction(playerid: str):
    result = predict_player_points(playerid)
    if isinstance(result, dict) and "error" in result:
        return result
    if isinstance(result, dict) and "predicted_points" in result:
        return float(result["predicted_points"])
    return {"error": "Unexpected response from prediction service", "player_id": playerid}


#Returns predictions for multiple players in a single request (batch endpoint)
#http://localhost:8000/api/nba/predictions/players/batch/?player_ids=1629029,201935,203507
@app.get("/api/nba/predictions/players/batch/")
async def batch_player_predictions(player_ids: str = Query(..., description="Comma-separated player IDs")):
    """
    Batch endpoint to get predictions for multiple players at once.
    Much more efficient than making individual requests.
    """
    ids = [pid.strip() for pid in player_ids.split(",") if pid.strip()]
    
    if not ids:
        return {"error": "No player IDs provided", "predictions": {}}
    
    # Limit batch size to prevent overload
    if len(ids) > 25:
        ids = ids[:25]
    
    loop = asyncio.get_event_loop()
    
    # Run predictions in thread pool to avoid blocking
    async def get_prediction(pid: str):
        try:
            result = await loop.run_in_executor(_executor, predict_player_points, pid)
            if isinstance(result, dict) and "predicted_points" in result:
                return (pid, float(result["predicted_points"]))
            elif isinstance(result, dict) and "error" in result:
                return (pid, {"error": result["error"]})
            return (pid, None)
        except Exception as e:
            return (pid, {"error": str(e)})
    
    # Run all predictions concurrently
    tasks = [get_prediction(pid) for pid in ids]
    results = await asyncio.gather(*tasks)
    
    predictions = {pid: value for pid, value in results}
    return {"predictions": predictions}


#Returns injury data for a specific team by team ID
#http://localhost:8000/api/nba/injuries/?teamid=1610612761
@app.get("/api/nba/injuries/")
async def team_injuries(teamid: str):
    """Get current injury report for a team from ESPN."""
    try:
        team_id_int = int(teamid)
        team_abbr = TEAM_ID_TO_ABBR.get(team_id_int)
        if not team_abbr:
            return {"injuries": [], "error": f"Unknown team ID: {teamid}"}

        loop = asyncio.get_event_loop()
        injuries_df = await loop.run_in_executor(_executor, fetch_espn_injuries, team_abbr.lower())

        if injuries_df.empty:
            return {"injuries": []}

        injuries_list = injuries_df[["PLAYER_NAME", "STATUS", "REASON"]].to_dict(orient="records")
        return {"injuries": injuries_list}
    except Exception as e:
        logger.error(f"Error fetching injuries for team {teamid}: {e}")
        return {"injuries": [], "error": str(e)}
