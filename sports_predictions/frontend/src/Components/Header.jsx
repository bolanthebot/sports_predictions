import { Link, useLocation } from "react-router-dom";

function Header() {
  const { pathname } = useLocation();
  const isNBA = pathname.startsWith("/nba");
  const isMLB = pathname.startsWith("/mlb");

  return (
    <header className="panel mb-4 sm:mb-6 px-4 py-3 sm:px-6 sm:py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-lg px-2 py-1 text-slate-100 transition-colors hover:bg-slate-700/40"
        >
          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-orange-300">
            Sports
          </span>
          <h1 className="text-lg font-bold sm:text-2xl">Predictions</h1>
        </Link>
        <nav className="flex items-center gap-2">
          <Link
            to="/nba"
            className={`rounded-md px-3 py-1.5 text-sm font-semibold transition-colors ${
              isNBA ? "bg-orange-500 text-slate-950" : "bg-slate-700/60 text-slate-200 hover:bg-slate-700"
            }`}
          >
            NBA
          </Link>
          <Link
            to="/mlb"
            className={`rounded-md px-3 py-1.5 text-sm font-semibold transition-colors ${
              isMLB ? "bg-orange-500 text-slate-950" : "bg-slate-700/60 text-slate-200 hover:bg-slate-700"
            }`}
          >
            MLB
          </Link>
        </nav>
      </div>
    </header>
  );
}

export default Header;
