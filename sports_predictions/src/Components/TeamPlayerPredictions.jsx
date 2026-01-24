import React, { useEffect, useState } from "react";
import PlayerPrediction from "./PlayerPrediction";

export default function TeamPlayerPredictions({ teamId }) {
  const [players, setPlayers] = useState([]);
  const [playerNames, setPlayerNames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTeamPlayers = async () => {
    try {
      setLoading(true);
      setError(null);

      if (!teamId) {
        setError("Missing team id");
        setPlayers([]);
        setPlayerNames([]);
        return;
      }

      const res = await fetch(
        `http://localhost:8000/api/nba/teamplayers/?teamid=${teamId}`
      );
      if (!res.ok) throw new Error("Failed to fetch team players");
      
      const data = await res.json();
      const playerIds = data[0];
      const playerName = data[1];
      setPlayers(playerIds || []);
      setPlayerNames(playerName || []);
    } catch (err) {
      setError(err.message);
      setPlayers([]);
      setPlayerNames([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTeamPlayers();
  }, [teamId]);

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
            <PlayerPrediction playerId={playerId} />
          </div>
        ))}
      </div>
    </div>
  );
}
