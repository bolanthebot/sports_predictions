import { useEffect, useRef, useState } from "react";
import { fetchAPI, API_ENDPOINTS } from "../config/api.js";

export default function MLBTeamPlayerPredictions({ teamId }) {
  const [players, setPlayers] = useState([]);
  const [playerNames, setPlayerNames] = useState([]);
  const [predictions, setPredictions] = useState({});
  const [loading, setLoading] = useState(true);
  const [predictionsLoading, setPredictionsLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);

  const fetchBatchPredictions = async (playerIds) => {
    try {
      setPredictionsLoading(true);
      abortControllerRef.current = new AbortController();
      const data = await fetchAPI(API_ENDPOINTS.mlb.predictions.playerBatch, {
        params: { player_ids: playerIds.join(","), stat: "hits" },
        signal: abortControllerRef.current.signal,
      });
      setPredictions(data.predictions || {});
    } catch (err) {
      if (err.name !== "AbortError") console.error(err);
    } finally {
      setPredictionsLoading(false);
    }
  };

  useEffect(() => {
    const fetchTeamPlayers = async () => {
      try {
        setLoading(true);
        setError(null);
        setPredictions({});
        if (!teamId) {
          setError("Missing team id");
          return;
        }
        if (abortControllerRef.current) abortControllerRef.current.abort();
        const data = await fetchAPI(API_ENDPOINTS.mlb.teams.players, {
          params: { teamid: teamId },
        });
        const ids = data[0] || [];
        const names = data[1] || [];
        setPlayers(ids);
        setPlayerNames(names);
        if (ids.length > 0) await fetchBatchPredictions(ids);
      } catch (err) {
        if (err.name !== "AbortError") setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchTeamPlayers();
    return () => abortControllerRef.current?.abort();
  }, [teamId]);

  const renderPrediction = (playerId) => {
    const pred = predictions[playerId];
    if (predictionsLoading) return <span className="text-gray-400">Loading...</span>;
    if (pred === null || pred === undefined) return <span className="text-gray-400">—</span>;
    if (typeof pred === "object" && pred.error) return <span className="text-red-400" title={pred.error}>Error</span>;
    if (typeof pred === "number") return <span className="text-blue-400 font-semibold">{pred.toFixed(1)} hits</span>;
    return <span className="text-gray-400">—</span>;
  };

  if (loading) return <div className="panel p-4 text-slate-300">Loading players...</div>;
  if (error) return <div className="panel p-4 text-red-300">Error: {error}</div>;
  if (!players?.length) return <div className="panel p-4 text-slate-300">No players found</div>;

  return (
    <div className="panel w-full p-4 sm:p-5">
      <h2 className="mb-3 text-lg font-bold text-white sm:mb-4 sm:text-xl">Batter Hit Predictions</h2>
      <div className="space-y-2">
        {players.map((playerId, index) => (
          <div key={playerId} className="flex items-center justify-between rounded-lg border border-slate-700/60 bg-slate-700/35 p-2.5 text-sm sm:p-3 sm:text-base">
            <span className="text-gray-300 truncate">{playerNames[index] || `Player ${playerId}`}</span>
            {renderPrediction(playerId)}
          </div>
        ))}
      </div>
    </div>
  );
}
