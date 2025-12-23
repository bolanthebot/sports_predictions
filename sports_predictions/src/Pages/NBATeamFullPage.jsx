import { useLocation, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import ObjectTable from "../Components/ObjectTable";

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

      const res = await fetch(
        "http://localhost:8000/api/nba/teams/?id=" + teamId
      );
      if (!res.ok) throw new Error("Failed to fetch team");

      const data = await res.json();
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

  console.log(teamGames);

  if (!team) return <div>Loading team {params.teamId}...</div>;

  return (
    // ADD CSS
    <div className="stuff">
      <h1 className="page-title">
        Team Page for {team.teamCity} {team.teamName}
      </h1>
      <h1 className="page-title">Key Dump:</h1>
      <ObjectTable data={team} />
      <h1 className="page-title">Game History:</h1>
      <ObjectTable data={teamGames} />
    </div>
  );
}
