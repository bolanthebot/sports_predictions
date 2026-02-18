import { useLocation, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import Header from "../Components/Header.jsx";
import ObjectTable from "../Components/ObjectTable.jsx";
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
    <div className="p-3 sm:p-4 md:p-6 flex flex-col min-h-screen bg-slate-900">
      <div className="w-full bg-slate-800 p-3 sm:p-4 md:p-6 rounded-lg">
        <div className="flex flex-col sm:flex-row text-2xl sm:text-3xl font-bold mb-4 text-white gap-2">
          <h1>
            {team.teamCity} {team.teamName}
          </h1>
          <h1 className="ml-2">- {team.teamTricode}</h1>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 sm:gap-x-12 gap-y-2 text-sm sm:text-md mb-6">
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
      <div className="w-full bg-slate-800 p-3 sm:p-4 md:p-6 rounded-lg mt-4 sm:mt-6">
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
      <div className="w-full mt-4 sm:mt-6">
        <TeamInjuries teamId={teamId} />
      </div>
      <div className="w-full mt-4 sm:mt-6">
        <TeamPlayerPredictions teamId={teamId} />
      </div>
    </div>
  );
}
