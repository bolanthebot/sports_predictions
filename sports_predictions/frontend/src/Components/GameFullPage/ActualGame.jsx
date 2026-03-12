import PredictionsMain from "../PredictionsMain";
import PredictionSlider from "../PredictionSlider";

export default function ActualGame(props) {
  const { game } = props;

  return (
    <div className="panel w-full p-4 sm:p-5 md:p-6">
      <h1 className="text-lg font-bold text-white sm:text-xl">Game Overview</h1>
      <p className="mb-3 text-xs font-semibold text-slate-300 sm:text-sm">
        {game.gameStatusText}
      </p>
      <div className="mb-2 grid grid-cols-1 items-start gap-4 sm:grid-cols-3">
        <div className="text-center sm:text-left w-full sm:w-auto">
          <p className="text-lg font-bold text-gray-200 sm:text-xl">
            {game.awayTeam.teamCity} {game.awayTeam.teamName}
          </p>
          <p className="text-3xl font-bold text-white">{game.awayTeam.score}</p>
          <PredictionsMain game={game.gameId} team={game.awayTeam.teamId} />
        </div>

        <span className="pt-2 text-center text-sm font-medium uppercase tracking-[0.2em] text-slate-400">
          vs
        </span>

        <div className="text-center sm:text-right w-full sm:w-auto">
          <p className="text-lg font-bold text-gray-200 sm:text-xl">
            {game.homeTeam.teamCity} {game.homeTeam.teamName}
          </p>
          <p className="text-3xl font-bold text-white">{game.homeTeam.score}</p>
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
        <p className="mt-3 text-center font-medium text-slate-300">
          {game.gameClock} - Q{game.period}
        </p>
      )}
      {game.gameLeaders.awayLeaders.name && (
        <div className="mt-4 rounded-lg border border-slate-700/70 bg-slate-900/30 p-3 text-sm">
          <h1 className="mb-1 font-bold text-gray-200">Top Scorers</h1>
          <p className="text-slate-400">
            <span className="font-semibold text-gray-200">
              {game.gameLeaders.awayLeaders.teamTricode}
            </span>{" "}
            {game.gameLeaders.awayLeaders.name} —{" "}
            {game.gameLeaders.awayLeaders.points} pts
          </p>
          <p className="text-slate-400">
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
