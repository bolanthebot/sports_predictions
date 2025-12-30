import React, { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import ObjectTable from "../Components/ObjectTable";
import PredictionsMain from "../Components/PredictionsMain.jsx";
import PredictionSlider from "../Components/PredictionSlider.jsx";

export default function NBAGameFullPage() {
  const { state } = useLocation();
  const params = useParams();
  const [game, setGame] = useState(state?.game || null);
  const [loading, setLoading] = useState(!state?.game);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (state?.game) return;

    const fetchGame = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("http://localhost:8000/api/nba/games/today");
        if (!res.ok) throw new Error("Failed to fetch games");
        const data = await res.json();
        const games = data.scoreboard?.games || [];
        const found = games.find(
          (g) => String(g.gameId) === String(params.gameId)
        );
        if (found) setGame(found);
        else setError("Game not found");
      } catch (err) {
        setError(err.message || "Error fetching game");
      } finally {
        setLoading(false);
      }
    };

    fetchGame();
  }, [params.gameId, state]);

  if (loading) return <div>Loading game {params.gameId}...</div>;
  if (error) return <div className="p-4 text-red-400">{error}</div>;
  if (!game) return <div>No game data</div>;

  console.log(game);
  return (
    <div className="bg-slate-900 min-h-screen flex flex-col px-4">
      <div className="max-w-md bg-slate-800 p-4 items-center">
        <p className="mb-2 text-sm font-semibold text-gray-300">
          {game.gameStatusText}
        </p>
        <div className="flex items-center justify-between">
          <div className="text-left">
            <p className="text-gray-200 text-xl font-bold">
              {game.awayTeam.teamCity} {game.awayTeam.teamName}
            </p>
            <p className="text-white text-3xl font-bold">
              {game.awayTeam.score}
            </p>
            <PredictionsMain game={game.gameId} team={game.awayTeam.teamId} />
          </div>

          <span className="text-sm font-medium text-gray-300">vs</span>

          <div className="text-right">
            <p className="text-gray-200 text-xl font-bold">
              {game.homeTeam.teamCity} {game.homeTeam.teamName}
            </p>
            <p className="text-white text-3xl font-bold">
              {game.homeTeam.score}
            </p>
            <PredictionsMain game={game.gameId} team={game.homeTeam.teamId} />
          </div>
        </div>
        {/* <div className="flex flex-col items-center mt-4">
          <PredictionSlider
            away={0.64}
            home={0.35}
            linelength={400}
            lineheight={8}
            dotSize={20}
          />
        </div>
 */}
        {game.gameClock && (
          <p className="mt-2 text-center text-gray-300 font-medium">
            {game.gameClock} - Q{game.period}
          </p>
        )}
        {game.gameLeaders.awayLeaders.name && (
          <div className="mt-3 space-y-1 text-sm">
            <h1 className="text-gray-200 font-bold">Top Scorers:</h1>
            <p className="text-gray-400">
              <span className="font-semibold text-gray-200">
                {game.gameLeaders.awayLeaders.teamTricode}
              </span>{" "}
              {game.gameLeaders.awayLeaders.name} —{" "}
              {game.gameLeaders.awayLeaders.points} pts
            </p>
            <p className="text-gray-400">
              <span className="font-semibold text-gray-200">
                {game.gameLeaders.homeLeaders.teamTricode}
              </span>{" "}
              {game.gameLeaders.homeLeaders.name} —{" "}
              {game.gameLeaders.homeLeaders.points} pts
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
