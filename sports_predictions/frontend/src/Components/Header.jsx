import { Link } from "react-router-dom";

function Header() {
  return (
    <header className="panel mb-4 sm:mb-6 px-4 py-3 sm:px-6 sm:py-4">
      <Link
        to="/"
        className="inline-flex items-center gap-2 rounded-lg px-2 py-1 text-slate-100 transition-colors hover:bg-slate-700/40"
      >
        <span className="text-xs font-semibold uppercase tracking-[0.2em] text-orange-300">
          NBA
        </span>
        <h1 className="text-lg font-bold sm:text-2xl">Sports Predictions</h1>
      </Link>
    </header>
  );
}

export default Header;
