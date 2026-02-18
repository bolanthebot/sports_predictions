import React from "react";

export default function ObjectTable({ data }) {
  if (data === null || data === undefined) return <span>{String(data)}</span>;

  // handle objects and display their keys & values recursively in a table
  // mainly for data visualization
  if (typeof data === "object") {
    return (
      <table className="w-full text-sm sm:text-base border-collapse">
        <tbody>
          {Object.entries(data).map(([key, value]) => (
            <tr key={key} className="border-b border-slate-600 hover:bg-slate-700/30">
              <td className="py-2 px-2 sm:px-3 text-slate-300 font-semibold">{key}</td>
              <td className="py-2 px-2 sm:px-3 text-slate-100">
                {typeof value === "object" && value !== null ? (
                  <ObjectTable data={value} />
                ) : (
                  String(value)
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return <span>{String(data)}</span>;
}
