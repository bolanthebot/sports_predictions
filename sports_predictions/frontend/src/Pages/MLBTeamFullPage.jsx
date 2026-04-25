import { useLocation, useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import KeyRow from "../Components/KeyRow.jsx";
import TeamInjuries from "../Components/TeamInjuries.jsx";
import MLBTeamPlayerPredictions from "../Components/MLBTeamPlayerPredictions.jsx";
import { fetchAPI, API_ENDPOINTS } from "../config/api.js";

export default function MLBTeamFullPage() {
  const { state } = useLocation();
  const params = useParams();
  const team = state?.team;
  const teamId = params.teamId;

  const [teamGames, setTeamGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTeamGames = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchAPI(API_ENDPOINTS.mlb.teams.games, { params: { id: teamId } });
      setTeamGames(data || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    fetchTeamGames();
  }, [fetchTeamGames]);

  if (!team) return <div className="panel p-6 text-slate-300">Loading team {params.teamId}...</div>;

  const periodRows = (team.periods || []).slice(0, 9);

  return (
    <div className="flex flex-col gap-4 pb-6 sm:gap-6 sm:pb-8">
      <section className="panel w-full p-4 sm:p-5 md:p-6">
        <div className="mb-5 flex flex-col gap-1 text-2xl font-bold text-white sm:flex-row sm:items-baseline sm:gap-2 sm:text-3xl">
          <h1>{team.teamCity} {team.teamName}</h1>
          <h1 className="text-slate-300">- {team.teamTricode}</h1>
        </div>
        <div className="grid grid-cols-1 gap-x-10 gap-y-2 text-sm sm:grid-cols-2 sm:text-base">
          <KeyRow label="teamId" value={team.teamId} />
          <div></div>
          <KeyRow label="Wins" value={team.wins} />
          <KeyRow label="Losses" value={team.losses} />
          <p className="mt-2 font-bold text-white">Last/Current Game</p>
          <div></div>
          <KeyRow label="Runs" value={team.score} />
          <KeyRow label="Hits" value={team.hits ?? "—"} />
          <KeyRow label="Errors" value={team.errors ?? "—"} />
          <KeyRow label="Probable Starter" value={team.probablePitcher?.fullName ?? "TBD"} />
          <p className="mt-2 font-bold text-white">Inning Scores</p>
          <div></div>
          {periodRows.length > 0
            ? periodRows.map((periodData) => (
                <KeyRow key={periodData.period} label={`Inning ${periodData.period}`} value={periodData.score} />
              ))
            : <KeyRow label="Inning Scores" value="No inning data" />}
        </div>
      </section>

      <section className="panel w-full p-4 sm:p-5 md:p-6">
        <div className="mb-4 font-bold text-white"><h1>Game History (WIP)</h1></div>
        {loading ? (
          <p className="text-slate-300">Loading recent team games...</p>
        ) : error ? (
          <p className="text-red-300">Unable to load team games.</p>
        ) : (
          <p className="text-slate-300">Loaded {teamGames.length} team game records.</p>
        )}
      </section>

      <div className="w-full"><TeamInjuries teamId={teamId} sport="mlb" /></div>
      <div className="w-full"><MLBTeamPlayerPredictions teamId={teamId} /></div>
    </div>
  );
}
