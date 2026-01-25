import React, { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import ActualGame from "../Components/GameFullPage/ActualGame.jsx";
import { fetchAPI, API_ENDPOINTS } from "../config/api.js";

export default function NBAGameFullPage() {
  const { state } = useLocation();
  const params = useParams();
  const [game, setGame] = useState(state?.game || null);
  const [loading, setLoading] = useState(!state?.game);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (state?.game) return;

    const fetchGame = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchAPI(API_ENDPOINTS.games.today);
        const games = data.scoreboard?.games || [];
        const found = games.find(
          (g) => String(g.gameId) === String(params.gameId)
        );
        if (found) setGame(found);
        else setError("Game not found");
      } catch (err) {
        setError(err.message || "Error fetching game");
      } finally {
        setLoading(false);
      }
    };

    fetchGame();
  }, [params.gameId, state]);

  if (loading) return <div>Loading game {params.gameId}...</div>;
  if (error) return <div className="p-4 text-red-400">{error}</div>;
  if (!game) return <div>No game data</div>;

  return (
    <div className="bg-slate-900 flex flex-col px-4">
      <ActualGame game={game} />
    </div>
  );
}
