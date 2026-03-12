import React, { useCallback, useEffect, useState } from "react";
import { fetchPrediction as fetchPredictionAPI, API_ENDPOINTS } from "../config/api.js";

export default function PredictionsMain(props) {
  const ids = props.ids || { gameId: props.game, teamId: props.team };
  const gameid = ids?.gameId;
  const teamid = ids?.teamId;

  const [prediction, setPrediction] = useState([]);
  const [loading, setLoading] = useState(true);
  const [warmingUp, setWarmingUp] = useState(false);
  const [error, setError] = useState(null);

  const fetchPrediction = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      if (!gameid || !teamid) {
        setError("Missing game or team id");
        setPrediction([]);
        return;
      }

      const { data, warmingUp: isWarmingUp } = await fetchPredictionAPI(
        API_ENDPOINTS.predictions.today,
        { params: { gameid, teamid } }
      );

      setWarmingUp(isWarmingUp);
      if (!isWarmingUp) {
        setPrediction(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [gameid, teamid]);

  useEffect(() => {
    fetchPrediction();
  }, [fetchPrediction]);

  const wp = prediction?.win_probability || 0;
  const pp = prediction?.predicted_team_points || 0;

  let percent = wp * 100;
  percent = percent.toFixed(2) + "%";
  let predicted_points = Math.round(pp * 10) / 10;

  if (loading) return <p className="text-sm text-slate-400">Loading prediction...</p>;
  if (warmingUp) return <p className="text-sm text-yellow-300">Generating predictions...</p>;
  if (error) return <p className="text-sm text-red-300">{error}</p>;
  return (
    <div className="mt-1 text-sm">
      <p className="text-slate-400">Win Chance: {percent}</p>
      <p className="text-slate-400">Predicted Points: {predicted_points}</p>
    </div>
  );
}
