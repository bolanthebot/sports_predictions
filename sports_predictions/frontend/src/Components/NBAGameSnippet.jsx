import { Link } from "react-router-dom";

const TEAM_COLORS = {
  ATL: "#E03A3E",
  BKN: "#000000",
  BOS: "#007A33",
  CHA: "#1D1160",
  CHI: "#CE1141",
  CLE: "#6F263D",
  DAL: "#00538C",
  DEN: "#0E2240",
  DET: "#C8102E",
  GSW: "#1D428A",
  HOU: "#CE1141",
  IND: "#002D62",
  LAC: "#C8102E",
  LAL: "#552583",
  MEM: "#5D76A9",
  MIA: "#98002E",
  MIL: "#00471B",
  MIN: "#0C2340",
  NOP: "#0C2340",
  NYK: "#006BB6",
  OKC: "#007AC1",
  ORL: "#0077C0",
  PHI: "#006BB6",
  PHX: "#1D1160",
  POR: "#E03A3E",
  SAC: "#5A2D81",
  SAS: "#C4CED4",
  TOR: "#CE1141",
  UTA: "#002B5C",
  WAS: "#002B5C",
};

function getRgbFromHex(hex) {
  const normalized = hex.replace("#", "");
  const value = parseInt(normalized, 16);
  return {
    r: (value >> 16) & 255,
    g: (value >> 8) & 255,
    b: value & 255,
  };
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
    primaryText: {
      color: isLightColor ? "#0f172a" : "#f8fafc",
    },
    secondaryText: {
      color: isLightColor ? "rgba(15, 23, 42, 0.75)" : "rgba(248, 250, 252, 0.76)",
    },
  };
}

function NBAGameSnippet(props) {
  const { game } = props;
  const getGameStatus = (game) => {
    if (game.gameStatus === 1) return "Scheduled";
    if (game.gameStatus === 2) return "Live";
    if (game.gameStatus === 3) return "Final";
    return game.gameStatusText;
  };

  const status = getGameStatus(game);
  const gameStatus = game.gameStatus;
  const awayTeam = `${game.awayTeam.teamCity} ${game.awayTeam.teamName}`;
  const homeTeam = `${game.homeTeam.teamCity} ${game.homeTeam.teamName}`;
  const awayScore = game.awayTeam.score || 0;
  const homeScore = game.homeTeam.score || 0;
  const awayRecord = `${game.awayTeam.wins}-${game.awayTeam.losses}`;
  const homeRecord = `${game.homeTeam.wins}-${game.homeTeam.losses}`;
  const awayStyles = getTeamButtonStyles(game.awayTeam.teamTricode);
  const homeStyles = getTeamButtonStyles(game.homeTeam.teamTricode);

  return (
    <article className="panel px-4 py-3 transition-colors hover:border-orange-400/60">
      <Link to={`/game/${game.gameId}`} state={{ game: game }} className="block">
        <div className="mb-4 flex items-center justify-between text-sm">
          <span className="text-slate-400">{game.gameStatusText}</span>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
              status === "Live"
                ? "animate-pulse bg-red-600 text-white"
                : status === "Final"
                ? "bg-slate-700 text-slate-200"
                : "bg-blue-500 text-white"
            }`}
          >
            {status}
          </span>
        </div>

        <div className="mb-1 text-xs uppercase tracking-[0.12em] text-slate-500">
          View game details
        </div>
      </Link>

      <div className="flex flex-col gap-3">
        <Link
          to={`/team/${game.awayTeam.teamId}`}
          state={{ team: game.awayTeam }}
          className="rounded-lg border p-3 transition-[filter] duration-150 hover:brightness-110"
          style={awayStyles.container}
        >
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <p className="font-medium" style={awayStyles.primaryText}>
                {awayTeam}
              </p>
              <span className="text-xs" style={awayStyles.secondaryText}>
                {awayRecord}
              </span>
            </div>
            <span className="text-2xl font-bold" style={awayStyles.primaryText}>
              {gameStatus === 1 ? "—" : awayScore}
            </span>
          </div>
        </Link>

        <Link
          to={`/team/${game.homeTeam.teamId}`}
          state={{ team: game.homeTeam }}
          className="rounded-lg border p-3 transition-[filter] duration-150 hover:brightness-110"
          style={homeStyles.container}
        >
          <div className="flex items-center justify-between">
            <div className="flex flex-col">
              <p className="font-medium" style={homeStyles.primaryText}>
                {homeTeam}
              </p>
              <span className="text-xs" style={homeStyles.secondaryText}>
                {homeRecord}
              </span>
            </div>
            <span className="text-2xl font-bold" style={homeStyles.primaryText}>
              {gameStatus === 1 ? "—" : homeScore}
            </span>
          </div>
        </Link>
      </div>
    </article>
  );
}

export default NBAGameSnippet;
