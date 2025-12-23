import { useLocation, useParams } from "react-router-dom";
import ObjectTable from "../Components/ObjectTable";

export default function NBAGameFullPage() {
  const { state } = useLocation();
  const params = useParams();
  const game = state?.game;

  if (!game) return <div>Loading game {params.gameId}...</div>;
  console.log(game);
  return (
    // ADD CSS
    <div className="stuff">
      <h1 className="page-title">Main Stuff:</h1>
      <h1 className="more stuff">
        {game.homeTeam.teamName} vs {game.awayTeam.teamName}
      </h1>
      <p>
        Status:{" "}
        {game.gameStatus === 1
          ? "Scheduled"
          : game.gameStatus === 2
          ? "Live"
          : "Final"}
      </p>
      <p>Status Details: {game.gameStatusText}</p>
      <p>
        Score: {game.awayTeam.score} — {game.homeTeam.score}
      </p>
      <h1 className="page-title">Key Dump:</h1>
      <ObjectTable data={game} />
    </div>
  );
}
