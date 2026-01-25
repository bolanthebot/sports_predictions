import React, { useEffect, useState, useRef } from "react";
import { fetchAPI, API_ENDPOINTS } from "../config/api.js";

export default function TeamPlayerPredictions({ teamId }) {
  const [players, setPlayers] = useState([]);
  const [playerNames, setPlayerNames] = useState([]);
  const [predictions, setPredictions] = useState({});
  const [loading, setLoading] = useState(true);
  const [predictionsLoading, setPredictionsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Abort controller to cancel in-flight requests
  const abortControllerRef = useRef(null);

  const fetchTeamPlayers = async () => {
    try {
      setLoading(true);
      setError(null);
      setPredictions({});

      if (!teamId) {
        setError("Missing team id");
        setPlayers([]);
        setPlayerNames([]);
        return;
      }

      // Cancel any pending prediction request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const data = await fetchAPI(API_ENDPOINTS.teams.players, {
        params: { teamid: teamId }
      });
      
      const playerIds = data[0] || [];
      const playerName = data[1] || [];
      setPlayers(playerIds);
      setPlayerNames(playerName);
      
      // Fetch all predictions in one batch request
      if (playerIds.length > 0) {
        await fetchBatchPredictions(playerIds);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message);
        setPlayers([]);
        setPlayerNames([]);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchBatchPredictions = async (playerIds) => {
    try {
      setPredictionsLoading(true);
      
      // Create new abort controller for this request
      abortControllerRef.current = new AbortController();
      
      const idsParam = playerIds.join(",");
      const data = await fetchAPI(API_ENDPOINTS.predictions.playerBatch, {
        params: { player_ids: idsParam },
        signal: abortControllerRef.current.signal
      });
      
      setPredictions(data.predictions || {});
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error("Error fetching batch predictions:", err);
        // Don't set error state - predictions are optional
      }
    } finally {
      setPredictionsLoading(false);
    }
  };

  useEffect(() => {
    fetchTeamPlayers();
    
    // Cleanup: abort any pending requests when component unmounts or teamId changes
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [teamId]);

  const renderPrediction = (playerId) => {
    const pred = predictions[playerId];
    
    if (predictionsLoading) {
      return <span className="text-gray-400">Loading...</span>;
    }
    
    if (pred === null || pred === undefined) {
      return <span className="text-gray-400">—</span>;
    }
    
    if (typeof pred === "object" && pred.error) {
      return <span className="text-red-400" title={pred.error}>Error</span>;
    }
    
    if (typeof pred === "number") {
      return (
        <span className="text-blue-400 font-semibold">
          {pred.toFixed(1)} pts
        </span>
      );
    }
    
    return <span className="text-gray-400">—</span>;
  };

  if (loading) return <div className="text-gray-400">Loading players...</div>;
  if (error) return <div className="text-red-400">Error: {error}</div>;
  if (!players || players.length === 0)
    return <div className="text-gray-400">No players found</div>;
  
  return (
    <div className="bg-slate-800 p-4 rounded-lg">
      <h2 className="text-white font-bold mb-4">Player Point Predictions</h2>
      <div className="space-y-2">
        {players.map((playerId, index) => (
          <div
            key={playerId}
            className="flex justify-between items-center p-2 bg-slate-700 rounded"
          >
            <span className="text-gray-300">{playerNames[index] || `Player ${playerId}`}</span>
            {renderPrediction(playerId)}
          </div>
        ))}
      </div>
    </div>
  );
}
