import { useLocation, useParams } from "react-router-dom";
import { useCallback, useEffect, useState } from "react";
import KeyRow from "../Components/KeyRow.jsx";
import TeamPlayerPredictions from "../Components/TeamPlayerPredictions.jsx";
import TeamInjuries from "../Components/TeamInjuries.jsx";
import { fetchAPI, API_ENDPOINTS } from "../config/api.js";

export default function NBATeamFullPage() {
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

      const data = await fetchAPI(API_ENDPOINTS.teams.games, {
        params: { id: teamId }
      });
      const teamData = data || [];
      setTeamGames(teamData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    fetchTeamGames();
  }, [fetchTeamGames]);

  if (!team) {
    return <div className="panel p-6 text-slate-300">Loading team {params.teamId}...</div>;
  }

  const periodRows = (team.periods || []).slice(0, 4);

  return (
    <div className="flex flex-col gap-4 pb-6 sm:gap-6 sm:pb-8">
      <section className="panel w-full p-4 sm:p-5 md:p-6">
        <div className="mb-5 flex flex-col gap-1 text-2xl font-bold text-white sm:flex-row sm:items-baseline sm:gap-2 sm:text-3xl">
          <h1>
            {team.teamCity} {team.teamName}
          </h1>
          <h1 className="text-slate-300">- {team.teamTricode}</h1>
        </div>
        <div className="grid grid-cols-1 gap-x-10 gap-y-2 text-sm sm:grid-cols-2 sm:text-base">
          <KeyRow label="teamId" value={team.teamId} />
          <div></div>
          <KeyRow label="Wins" value={team.wins} />
          <KeyRow label="Losses" value={team.losses} />
          <p className="mt-2 font-bold text-white">Last/Current Game</p>
          <div></div>
          <KeyRow label="Score" value={team.score} />
          <KeyRow label="Seed" value={team.seed ?? "null"} />
          <KeyRow label="inBonus" value={team.inBonus} />
          <KeyRow label="Timeouts Remaining" value={team.timeoutsRemaining} />
          <p className="mt-2 font-bold text-white">Period Scores</p>
          <div></div>
          {periodRows.length > 0 ? (
            periodRows.map((periodData) => (
              <KeyRow
                key={periodData.period}
                label={"Period " + periodData.period}
                value={periodData.score}
              />
            ))
          ) : (
            <KeyRow label="Period Scores" value="No period data" />
          )}
        </div>
      </section>
      <section className="panel w-full p-4 sm:p-5 md:p-6">
        <div className="mb-4 font-bold text-white">
          <h1>Game History (WIP)</h1>
        </div>
        {loading ? (
          <p className="text-slate-300">Loading recent team games...</p>
        ) : error ? (
          <p className="text-red-300">Unable to load team games.</p>
        ) : (
          <p className="text-slate-300">
            Loaded {teamGames.length} team game records.
          </p>
        )}
        {/* <div className="mb-6 grid grid-cols-1 gap-x-12 gap-y-2 text-md">
          <KeyRow label="Total Games" value={teamGames.length} />
          {teamGames.map((game) => (
            <li>{game.Game_ID}</li>
          ))}
        </div> */}
      </section>
      <div className="w-full">
        <TeamInjuries teamId={teamId} />
      </div>
      <div className="w-full">
        <TeamPlayerPredictions teamId={teamId} />
      </div>
    </div>
  );
}
