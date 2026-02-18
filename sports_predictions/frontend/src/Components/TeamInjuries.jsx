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
      <div className="w-full bg-slate-800 p-3 sm:p-4 rounded-lg">
        <h2 className="text-white font-bold mb-3 sm:mb-4 text-lg sm:text-xl">
          Injury Report
        </h2>
        <div className="text-gray-400">Loading injuries...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full bg-slate-800 p-3 sm:p-4 rounded-lg">
        <h2 className="text-white font-bold mb-3 sm:mb-4 text-lg sm:text-xl">
          Injury Report
        </h2>
        <div className="text-red-400">Error loading injuries</div>
      </div>
    );
  }

  return (
    <div className="w-full bg-slate-800 p-3 sm:p-4 rounded-lg">
      <h2 className="text-white font-bold mb-3 sm:mb-4 text-lg sm:text-xl">
        Injury Report
      </h2>
      {injuries.length === 0 ? (
        <div className="text-green-400 text-sm sm:text-base">
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
                className="flex flex-col sm:flex-row sm:justify-between sm:items-center p-2 sm:p-3 bg-slate-700 rounded gap-1 sm:gap-2"
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
