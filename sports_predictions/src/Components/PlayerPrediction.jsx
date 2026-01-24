import React, { useEffect, useState } from "react";

export default function PlayerPrediction(props) {
  const { playerId, playerName } = props;
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPlayerPrediction = async () => {
    try {
      setLoading(true);
      setError(null);

      if (!playerId) {
        setError("Missing player id");
        setPrediction(null);
        return;
      }

      const url = `http://localhost:8000/api/nba/predictions/player/today/?playerid=${playerId}`;
      const res = await fetch(url);
      
      if (!res.ok) throw new Error("Failed to fetch player prediction");

      const data = await res.json();
      setPrediction(data);
    } catch (err) {
      setError(err.message);
      setPrediction(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlayerPrediction();
  }, [playerId]);

  if (loading) return <span className="text-gray-400">Loading...</span>;
  if (error) return <span className="text-red-400">Error: {error}</span>;
  if (!prediction) return <span className="text-gray-400">—</span>;

  const predictionValue =
    typeof prediction === "number"
      ? prediction
      : typeof prediction?.predicted_points === "number"
      ? prediction.predicted_points
      : null;

  if (prediction?.error) {
    return (
      <span className="text-red-400">
        Error: {prediction.error || "Prediction failed"}
      </span>
    );
  }

  if (predictionValue === null) {
    return <span className="text-gray-400">—</span>;
  }

  return (
    <span className="text-blue-400 font-semibold">
      {predictionValue.toFixed(1)} pts
    </span>
  );
}
