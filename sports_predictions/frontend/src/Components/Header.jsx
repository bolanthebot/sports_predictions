import { Link } from "react-router-dom";

function Header() {
  return (
    <div className="bg-slate-800 p-2 sm:p-4 mb-4 sm:mb-6">
      <Link to={"/"}>
        <div className="py-2 px-2 sm:px-4 hover:bg-slate-700/70 rounded-lg inline-block">
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-white">Sports Predictions</h1>
        </div>
      </Link>
    </div>
  );
}

export default Header;
