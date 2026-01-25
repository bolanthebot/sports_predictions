import { useLocation, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import Header from "../Components/Header.jsx";
import ObjectTable from "../Components/ObjectTable";
import KeyRow from "../Components/KeyRow.jsx";
import TeamPlayerPredictions from "../Components/TeamPlayerPredictions.jsx";
import { fetchAPI, API_ENDPOINTS } from "../config/api.js";

export default function NBATeamFullPage() {
  const { state } = useLocation();
  const params = useParams();
  const team = state?.team;
  const teamId = params.teamId;

  const [teamGames, setTeamGames] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchTeamGames = async () => {
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
  };

  useEffect(() => {
    fetchTeamGames();
  }, []);

  console.log(typeof teamGames);

  if (!team) return <div>Loading team {params.teamId}...</div>;

  return (
    // ADD CSS
    <div className="p-4 flex flex-col">
      <div className="min-w-2xl max-w-1/2 bg-slate-800 p-4 items-center">
        <div className="flex text-3xl font-bold mb-4 text-white">
          <h1>
            {team.teamCity} {team.teamName}
          </h1>
          <h1 className="ml-2">- {team.teamTricode}</h1>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-12 gap-y-2 text-md mb-6">
          <KeyRow label="teamId" value={team.teamId} />
          <div></div>
          <KeyRow label="Wins" value={team.wins} />
          <KeyRow label="Losses" value={team.losses} />
          <p className="text-white font-bold">Last/Current Game</p>
          <div></div>
          <KeyRow label="Score" value={team.score} />
          <KeyRow label="Seed" value={team.seed ?? "null"} />
          <KeyRow label="inBonus" value={team.inBonus} />
          <KeyRow label="Timouts Remaining" value={team.timeoutsRemaining} />
          <p className="text-white font-bold">Period Scores</p>
          <div></div>
          <KeyRow
            label={"Period " + team.periods[0].period}
            value={team.periods[0].score}
          />
          <KeyRow
            label={"Period " + team.periods[1].period}
            value={team.periods[1].score}
          />
          <KeyRow
            label={"Period " + team.periods[2].period}
            value={team.periods[2].score}
          />
          <KeyRow
            label={"Period " + team.periods[3].period}
            value={team.periods[3].score}
          />
        </div>
      </div>
      <div className="min-w-2xl max-w-1/2 bg-slate-800 p-4 items-center mt-6">
        <div className="text-white font-bold mb-4">
          <h1>Game History WIP</h1>
        </div>
        {/* <div className="grid grid-cols-1 gap-x-12 gap-y-2 text-md mb-6">
          <KeyRow label="Total Games" value={teamGames.length} />
          {teamGames.map((game) => (
            <li>{game.Game_ID}</li>
          ))}
        </div> */}
      </div>
      <div className="min-w-2xl max-w-1/2 mt-6">
        <TeamPlayerPredictions teamId={teamId} />
      </div>
    </div>
  );
}
