
import { useEffect, useState } from "react";

export default function DailyNBAGames() {
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchGames = async () => {
    try {
      setLoading(true);
      setError(null);

      const res = await fetch("http://localhost:8000/api/nba/games/today");
      if (!res.ok) throw new Error("Failed to fetch games");

      const data = await res.json();
      
      // Extract games from the nested structure
      const gamesData = data.scoreboard?.games || [];
      setGames(gamesData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGames();
  }, []);

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 p-4">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl text-center font-bold text-white ">NBA Games Today</h1>
          <button
            onClick={fetchGames}
            className="px-6 py-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold rounded-lg transition-colors"
          >
            Refresh
          </button>
        </div>

        {loading && (
          <p className="text-center text-gray-300 text-lg">Loading games...</p>
        )}
        
        {error && (
          <p className="text-center text-red-400 bg-red-900/30 p-4 rounded-lg">
            {error}
          </p>
        )}

        {!loading && !error && games.length === 0 && (
          <p className="text-center text-gray-400 text-lg">
            No games scheduled for today
          </p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {games.map((game) => {
            const status = getGameStatus(game);
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
                <div className="flex justify-between items-center mb-4 text-sm">
                  <span className="text-gray-400">
                    {formatTime(game.gameStatusText)}
                  </span>
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

                <div className="space-y-3">
                  <div className="flex justify-between items-center p-2 rounded bg-slate-700/50">
                    <div className="flex flex-col">
                      <span className="text-white font-medium">{awayTeam}</span>
                      <span className="text-xs text-gray-400">{awayRecord}</span>
                    </div>
                    <span className="text-xl font-bold text-white">
                      {game.gameStatus === 1 ? "—" : awayScore}
                    </span>
                  </div>

                  <div className="flex justify-between items-center p-2 rounded bg-slate-700/50">
                    <div className="flex flex-col">
                      <span className="text-white font-medium">{homeTeam}</span>
                      <span className="text-xs text-gray-400">{homeRecord}</span>
                    </div>
                    <span className="text-xl font-bold text-white">
                      {game.gameStatus === 1 ? "—" : homeScore}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
