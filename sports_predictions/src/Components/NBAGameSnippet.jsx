import { Link } from "react-router-dom";

function NBAGameSnippet(props) {
  const { game } = props;
  const getGameStatus = (game) => {
    if (game.gameStatus === 1) return "Scheduled";
    if (game.gameStatus === 2) return "Live";
    if (game.gameStatus === 3) return "Final";
    return game.gameStatusText;
  };

  const formatTime = (timeString) => {
    // Convert "3:30 pm ET" format or use as-is
    return timeString;
  };

  const status = getGameStatus(game);
  const gameStatus = game.gameStatus;
  const awayTeam = `${game.awayTeam.teamCity} ${game.awayTeam.teamName}`;
  const homeTeam = `${game.homeTeam.teamCity} ${game.homeTeam.teamName}`;
  const awayScore = game.awayTeam.score || 0;
  const homeScore = game.homeTeam.score || 0;
  const awayRecord = `${game.awayTeam.wins}-${game.awayTeam.losses}`;
  const homeRecord = `${game.homeTeam.wins}-${game.homeTeam.losses}`;

  return (
    <div
      key={game.gameId}
      className="bg-slate-800/50 backdrop-blur-sm rounded-xl p-4 border border-slate-700 hover:border-purple-500 transition-colors"
    >
      <Link to={`/game/${game.gameId}`} state={{ game: game }}>
        <div className="flex justify-between items-center mb-4 text-sm">
          <span className="text-gray-400">{game.gameStatusText}</span>
          <span
            className={`px-3 py-1 rounded-full font-semibold ${
              status === "Live"
                ? "bg-red-600 text-white animate-pulse"
                : status === "Final"
                ? "bg-gray-600 text-gray-200"
                : "bg-blue-600 text-white"
            }`}
          >
            {status}
          </span>
        </div>

        <div className="flex flex-col gap-y-3">
          <Link
            to={`/team/${game.awayTeam.teamId}`}
            state={{ team: game.awayTeam }}
          >
            <div className="flex justify-between items-center p-2 rounded bg-slate-700/50 hover:bg-slate-700/90">
              <div className="flex flex-col">
                <p
                  to={`/team/${game.awayTeam.teamId}`}
                  state={{ team: game.awayTeam }}
                  className="text-white font-medium"
                >
                  {awayTeam}
                </p>
                <span className="text-xs text-gray-400">{awayRecord}</span>
              </div>
              <span className="text-xl font-bold text-white">
                {gameStatus === 1 ? "—" : awayScore}
              </span>
            </div>
          </Link>

          <Link
            to={`/team/${game.homeTeam.teamId}`}
            state={{ team: game.homeTeam }}
          >
            <div className="flex justify-between items-center p-2 rounded bg-slate-700/50 hover:bg-slate-700/90">
              <div className="flex flex-col">
                <p className="text-white font-medium">{homeTeam}</p>
                <span className="text-xs text-gray-400">{homeRecord}</span>
              </div>
              <span className="text-xl font-bold text-white">
                {gameStatus === 1 ? "—" : homeScore}
              </span>
            </div>
          </Link>
        </div>
      </Link>
    </div>
  );
}

export default NBAGameSnippet;
