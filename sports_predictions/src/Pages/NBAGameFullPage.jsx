import { useLocation, useParams } from "react-router-dom";
import ObjectTable from "../Components/ObjectTable";

export default function NBAGameFullPage() {
  const { state } = useLocation();
  const params = useParams();
  const game = state?.game;

  if (!game) return <div>Loading game {params.gameId}...</div>;
  console.log(game);
  return (
    <div className="min-h-screen flex flex-col bg-slate-900 px-4">
      <div className="max-w-md bg-slate-800 p-4">
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
          </div>

          <span className="text-sm font-medium text-gray-300">vs</span>

          <div className="text-right">
            <p className="text-gray-200 text-xl font-bold">
              {game.homeTeam.teamCity} {game.homeTeam.teamName}
            </p>
            <p className="text-white text-3xl font-bold">
              {game.homeTeam.score}
            </p>
          </div>
        </div>
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
