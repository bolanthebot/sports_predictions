import { useEffect, useState } from "react";
import { fetchAPI, API_ENDPOINTS } from "../config/api.js";

export default function MLBPlayerPrediction({ playerId, stat = "hits" }) {
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true);
        setError(null);
        if (!playerId) {
          setError("Missing player id");
          setPrediction(null);
          return;
        }
        const data = await fetchAPI(API_ENDPOINTS.mlb.predictions.playerToday, {
          params: { playerid: playerId, stat },
        });
        setPrediction(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [playerId, stat]);

  if (loading) return <span className="text-gray-400">Loading...</span>;
  if (error) return <span className="text-red-400">Error</span>;
  if (prediction?.error) return <span className="text-red-400">Error</span>;

  const value = typeof prediction === "number"
    ? prediction
    : prediction?.predicted_value ?? prediction?.predicted_hits ?? prediction?.predicted_strikeouts;
  if (value === null || value === undefined) return <span className="text-gray-400">—</span>;
  return (
    <span className="text-blue-400 font-semibold">
      {Number(value).toFixed(1)} {stat === "strikeouts" ? "Ks" : "hits"}
    </span>
  );
}
