import { useEffect, useState, useRef, useCallback } from "react";
import NBAGameSnippet from "./NBAGameSnippet.jsx";
import { fetchAPI, API_ENDPOINTS } from "../config/api.js";

// Debounce delay in milliseconds
const REFRESH_DEBOUNCE_MS = 2000;

export default function NBADailyGameGrid() {
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshDisabled, setRefreshDisabled] = useState(false);
  
  // Track in-flight requests to prevent duplicates
  const fetchingRef = useRef(false);
  const abortControllerRef = useRef(null);

  const fetchGames = useCallback(async () => {
    // Prevent duplicate concurrent requests
    if (fetchingRef.current) {
      return;
    }
    
    try {
      fetchingRef.current = true;
      setLoading(true);
      setError(null);
      
      // Cancel any previous request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      const data = await fetchAPI(API_ENDPOINTS.games.today, {
        signal: abortControllerRef.current.signal
      });

      // Extract games from the nested structure
      const gamesData = data.scoreboard?.games || [];
      setGames(gamesData);
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message);
      }
    } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, []);

  const handleRefresh = useCallback(() => {
    if (refreshDisabled) return;
    
    // Disable refresh button temporarily to prevent spam
    setRefreshDisabled(true);
    fetchGames();
    
    setTimeout(() => {
      setRefreshDisabled(false);
    }, REFRESH_DEBOUNCE_MS);
  }, [refreshDisabled, fetchGames]);

  useEffect(() => {
    fetchGames();
    
    // Cleanup on unmount
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchGames]);

  return (
    <div className="min-h-screen p-3 sm:p-4 md:p-6">
      <div className="w-full">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-4 mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl md:text-4xl text-center font-bold text-white ">
            NBA Games Today
          </h1>
          <button
            onClick={handleRefresh}
            disabled={refreshDisabled || loading}
            className={`px-6 py-2 font-semibold rounded-lg transition-colors ${
              refreshDisabled || loading
                ? "bg-gray-600 cursor-not-allowed text-gray-400"
                : "bg-orange-600 hover:bg-orange-700 text-white"
            }`}
          >
            {loading ? "Loading..." : refreshDisabled ? "Wait..." : "Refresh"}
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
