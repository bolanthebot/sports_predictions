import { useEffect, useState } from "react";
import NBAGameSnippet from "./NBAGameSnippet.jsx";

export default function NBADailyGameGrid() {
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 p-4">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl text-center font-bold text-white ">
            NBA Games Today
          </h1>
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
            return <NBAGameSnippet game={game} key={game.gameId} />;
          })}
        </div>
      </div>
    </div>
  );
}
