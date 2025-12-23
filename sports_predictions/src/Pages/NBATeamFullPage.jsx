import { useLocation, useParams } from "react-router-dom";
import ObjectTable from "../Components/ObjectTable";

export default function NBATeamFullPage() {
  const { state } = useLocation();
  const params = useParams();
  const team = state?.team;

  if (!team) return <div>Loading team {params.teamId}...</div>;
  console.log(team);

  return (
    // ADD CSS
    <div className="stuff">
      <h1 className="page-title">
        Team Page for {team.teamCity} {team.teamName}
      </h1>
      <h1 className="page-title">Key Dump:</h1>
      <ObjectTable data={team} />
    </div>
  );
}
