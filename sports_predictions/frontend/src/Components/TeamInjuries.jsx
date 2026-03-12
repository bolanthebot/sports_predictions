import React, { useEffect, useState } from "react";
import { fetchAPI, API_ENDPOINTS } from "../config/api.js";

const STATUS_COLORS = {
  Out: "bg-red-500/20 text-red-400 border-red-500/30",
  "Day-to-day": "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  Questionable: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  Probable: "bg-green-500/20 text-green-400 border-green-500/30",
  Doubtful: "bg-red-500/20 text-red-300 border-red-500/30",
};

export default function TeamInjuries({ teamId }) {
  const [injuries, setInjuries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!teamId) return;

    const fetchInjuries = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchAPI(API_ENDPOINTS.teams.injuries, {
          params: { teamid: teamId },
        });
        setInjuries(data.injuries || []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchInjuries();
  }, [teamId]);

  if (loading) {
    return (
      <div className="panel w-full p-4 sm:p-5">
        <h2 className="mb-3 text-lg font-bold text-white sm:mb-4 sm:text-xl">
          Injury Report
        </h2>
        <div className="text-slate-300">Loading injuries...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel w-full p-4 sm:p-5">
        <h2 className="mb-3 text-lg font-bold text-white sm:mb-4 sm:text-xl">
          Injury Report
        </h2>
        <div className="text-red-300">Error loading injuries</div>
      </div>
    );
  }

  return (
    <div className="panel w-full p-4 sm:p-5">
      <h2 className="mb-3 text-lg font-bold text-white sm:mb-4 sm:text-xl">
        Injury Report
      </h2>
      {injuries.length === 0 ? (
        <div className="text-sm text-green-300 sm:text-base">
          No injuries reported — full health
        </div>
      ) : (
        <div className="space-y-2">
          {injuries.map((injury, index) => {
            const statusClass =
              STATUS_COLORS[injury.STATUS] ||
              "bg-gray-500/20 text-gray-400 border-gray-500/30";
            return (
              <div
                key={index}
                className="flex flex-col gap-1 rounded-lg border border-slate-700/60 bg-slate-700/35 p-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-2 sm:p-3"
              >
                <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                  <span className="text-gray-200 font-medium truncate text-sm sm:text-base">
                    {injury.PLAYER_NAME}
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded border whitespace-nowrap ${statusClass}`}
                  >
                    {injury.STATUS}
                  </span>
                </div>
                <span className="text-gray-400 text-xs sm:text-sm truncate">
                  {injury.REASON}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
