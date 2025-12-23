import React from "react";

export default function ObjectTable({ data }) {
  if (data === null || data === undefined) return <span>{String(data)}</span>;

  // handle objects and display their keys & values recursively in a table
  // mainly for data visualization
  if (typeof data === "object") {
    return (
      <table>
        <tbody>
          {Object.entries(data).map(([key, value]) => (
            <tr key={key}>
              <td>{key}</td>
              <td>
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
