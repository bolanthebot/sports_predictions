import React, { useEffect, useState } from "react";

export default function PredictionsMain(props) {
  const ids = props.ids || { gameId: props.game, teamId: props.team };
  const gameid = ids?.gameId;
  const teamid = ids?.teamId;

  const [prediction, setPrediction] = useState([]);
  const [loading, setLoading] = useState(true);
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

      let url =
        "http://localhost:8000/api/nba/predictions/today/?gameid=" +
        gameid +
        "&teamid=" +
        teamid;

      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch games");

      const data = await res.json();
      setPrediction(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrediction();
  }, [gameid, teamid]);

  let percent = prediction * 100;
  percent = percent.toFixed(2) + "%";

  if (loading) return <p className="text-gray-700">Loading prediction...</p>;
  return <p className="text-gray-400">Prediction: {percent}</p>;
}
