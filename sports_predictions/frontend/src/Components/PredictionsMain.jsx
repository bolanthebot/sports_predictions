import React, { useEffect, useState } from "react";
import { fetchPrediction as fetchPredictionAPI, API_ENDPOINTS } from "../config/api.js";

export default function PredictionsMain(props) {
  const ids = props.ids || { gameId: props.game, teamId: props.team };
  const gameid = ids?.gameId;
  const teamid = ids?.teamId;

  const [prediction, setPrediction] = useState([]);
  const [loading, setLoading] = useState(true);
  const [warmingUp, setWarmingUp] = useState(false);
  const [error, setError] = useState(null);

  const fetchPrediction = async () => {
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
  };

  useEffect(() => {
    fetchPrediction();
  }, [gameid, teamid]);

  const wp = prediction?.win_probability || 0;
  const pp = prediction?.predicted_team_points || 0;

  let percent = wp * 100;
  percent = percent.toFixed(2) + "%";
  let predicted_points = Math.round(pp * 10) / 10;

  if (loading) return <p className="text-gray-400">Loading prediction...</p>;
  if (warmingUp) return <p className="text-yellow-400">Generating predictions, please wait...</p>;
  return (
    <div>
      <p className="text-gray-400">Win Chance: {percent}</p>
      <p className="text-gray-400">Predicted Points: {predicted_points}</p>
    </div>
  );
}
