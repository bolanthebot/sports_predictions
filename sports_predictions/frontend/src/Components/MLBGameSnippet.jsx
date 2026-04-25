import { Link } from "react-router-dom";
import PredictionsMain from "./PredictionsMain.jsx";

const TEAM_COLORS = {
  ARI: "#A71930", ATL: "#CE1141", BAL: "#DF4601", BOS: "#BD3039", CHC: "#0E3386",
  CWS: "#27251F", CIN: "#C6011F", CLE: "#E31937", COL: "#333366", DET: "#0C2340",
  HOU: "#EB6E1F", KC: "#004687", LAA: "#BA0021", LAD: "#005A9C", MIA: "#00A3E0",
  MIL: "#12284B", MIN: "#002B5C", NYM: "#002D72", NYY: "#0C2340", ATH: "#003831",
  PHI: "#E81828", PIT: "#FDB827", SD: "#2F241D", SF: "#FD5A1E", SEA: "#0C2C56",
  STL: "#C41E3A", TB: "#092C5C", TEX: "#003278", TOR: "#134A8E", WSH: "#AB0003",
};

function getRgbFromHex(hex) {
  const normalized = hex.replace("#", "");
  const value = parseInt(normalized, 16);
  return { r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255 };
}

function getTeamButtonStyles(teamTricode) {
  const baseColor = TEAM_COLORS[teamTricode] || "#334155";
  const { r, g, b } = getRgbFromHex(baseColor);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  const isLightColor = brightness > 150;
  return {
    container: {
      backgroundColor: `rgba(${r}, ${g}, ${b}, 0.25)`,
      borderColor: `rgba(${r}, ${g}, ${b}, 0.75)`,
    },
    primaryText: { color: isLightColor ? "#0f172a" : "#f8fafc" },
    secondaryText: { color: isLightColor ? "rgba(15, 23, 42, 0.75)" : "rgba(248, 250, 252, 0.76)" },
  };
}

export default function MLBGameSnippet({ game }) {
  const status = game.gameStatus === 1 ? "Scheduled" : game.gameStatus === 2 ? "Live" : "Final";
  const gameStatus = game.gameStatus;
  const awayTeam = `${game.awayTeam.teamCity} ${game.awayTeam.teamName}`;
  const homeTeam = `${game.homeTeam.teamCity} ${game.homeTeam.teamName}`;
  const awayRecord = `${game.awayTeam.wins}-${game.awayTeam.losses}`;
  const homeRecord = `${game.homeTeam.wins}-${game.homeTeam.losses}`;
  const awayStyles = getTeamButtonStyles(game.awayTeam.teamTricode);
  const homeStyles = getTeamButtonStyles(game.homeTeam.teamTricode);

  return (
    <article className="panel px-4 py-3 transition-colors hover:border-orange-400/60">
      <Link to={`/mlb/game/${game.gameId}`} state={{ game }} className="block">
        <div className="mb-4 flex items-center justify-between text-sm">
          <span className="text-slate-400">{game.gameStatusText}</span>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
            status === "Live" ? "animate-pulse bg-red-600 text-white"
              : status === "Final" ? "bg-slate-700 text-slate-200" : "bg-blue-500 text-white"
          }`}>{status}</span>
        </div>
        <div className="mb-1 text-xs uppercase tracking-[0.12em] text-slate-500">View game details</div>
      </Link>

      <div className="flex flex-col gap-3">
        <Link to={`/mlb/team/${game.awayTeam.teamId}`} state={{ team: game.awayTeam }} className="rounded-lg border p-3 transition-[filter] duration-150 hover:brightness-110" style={awayStyles.container}>
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <p className="font-medium" style={awayStyles.primaryText}>{awayTeam}</p>
              <span className="text-xs" style={awayStyles.secondaryText}>{awayRecord}</span>
              {game.awayTeam.probablePitcher?.fullName && (
                <span className="text-xs" style={awayStyles.secondaryText}>SP: {game.awayTeam.probablePitcher.fullName}</span>
              )}
            </div>
            <div className="text-right">
              <span className="block text-2xl font-bold" style={awayStyles.primaryText}>{gameStatus === 1 ? "—" : game.awayTeam.score || 0}</span>
              <PredictionsMain sport="mlb" game={game.gameId} team={game.awayTeam.teamId} />
            </div>
          </div>
        </Link>

        <Link to={`/mlb/team/${game.homeTeam.teamId}`} state={{ team: game.homeTeam }} className="rounded-lg border p-3 transition-[filter] duration-150 hover:brightness-110" style={homeStyles.container}>
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <p className="font-medium" style={homeStyles.primaryText}>{homeTeam}</p>
              <span className="text-xs" style={homeStyles.secondaryText}>{homeRecord}</span>
              {game.homeTeam.probablePitcher?.fullName && (
                <span className="text-xs" style={homeStyles.secondaryText}>SP: {game.homeTeam.probablePitcher.fullName}</span>
              )}
            </div>
            <div className="text-right">
              <span className="block text-2xl font-bold" style={homeStyles.primaryText}>{gameStatus === 1 ? "—" : game.homeTeam.score || 0}</span>
              <PredictionsMain sport="mlb" game={game.gameId} team={game.homeTeam.teamId} />
            </div>
          </div>
        </Link>
      </div>
    </article>
  );
}
