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
    <div className="pb-6 sm:pb-8">
      <div className="w-full">
        <div className="mb-6 flex flex-col gap-3 sm:mb-8 sm:flex-row sm:items-end sm:justify-between">
          <h1 className="text-2xl font-bold text-slate-100 sm:text-3xl md:text-4xl">
            NBA Games Today
          </h1>
          <button
            onClick={handleRefresh}
            disabled={refreshDisabled || loading}
            className={`rounded-lg px-5 py-2.5 text-sm font-semibold tracking-wide transition-colors ${
              refreshDisabled || loading
                ? "cursor-not-allowed bg-slate-700 text-slate-400"
                : "bg-orange-500 text-slate-950 hover:bg-orange-400"
            }`}
          >
            {loading ? "Loading..." : refreshDisabled ? "Wait..." : "Refresh"}
          </button>
        </div>

        {loading && (
          <p className="panel p-6 text-center text-lg text-slate-300">Loading games...</p>
        )}

        {error && (
          <p className="rounded-lg border border-red-500/40 bg-red-900/20 p-4 text-center text-red-300">
            {error}
          </p>
        )}

        {!loading && !error && games.length === 0 && (
          <p className="panel p-6 text-center text-lg text-slate-300">
            No games scheduled for today
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {games.map((game) => {
            return <NBAGameSnippet game={game} key={game.gameId} />;
          })}
        </div>
      </div>
    </div>
  );
}
