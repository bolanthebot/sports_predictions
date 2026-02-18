import PredictionsMain from "../PredictionsMain";
import PredictionSlider from "../PredictionSlider";

export default function ActualGame(props) {
  const { game } = props;

  return (
    <div className="w-full bg-slate-800 p-3 sm:p-4 md:p-6 items-center rounded-lg">
      <h1 className="text-white font-bold text-lg sm:text-xl">ACTUAL GAME:</h1>
      <p className="mb-2 text-xs sm:text-sm font-semibold text-gray-300">
        {game.gameStatusText}
      </p>
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-1">
        <div className="text-center sm:text-left w-full sm:w-auto">
          <p className="text-gray-200 text-lg sm:text-xl font-bold">
            {game.awayTeam.teamCity} {game.awayTeam.teamName}
          </p>
          <p className="text-white text-2xl sm:text-3xl font-bold">{game.awayTeam.score}</p>
          <PredictionsMain game={game.gameId} team={game.awayTeam.teamId} />
        </div>

        <span className="text-sm font-medium text-gray-300">vs</span>

        <div className="text-center sm:text-right w-full sm:w-auto">
          <p className="text-gray-200 text-lg sm:text-xl font-bold">
            {game.homeTeam.teamCity} {game.homeTeam.teamName}
          </p>
          <p className="text-white text-2xl sm:text-3xl font-bold">{game.homeTeam.score}</p>
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
  );
}
