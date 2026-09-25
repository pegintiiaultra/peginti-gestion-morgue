import React from "react";

export default function Sidebar() {
  const menu = [
    "1 - DEPOT",
    "2 - TRANSFERT",
    "3 - SORTIE INHUMATION",
    "4 - RECHERCHE RAPIDE",
    "5 - STATISTIQUES"
  ];
  const colors = ["#1E4D8B", "#E67E22", "#A93226", "#34495E", "#1E4D8B"];

  return (
    <div style={{ width: "220px", backgroundColor: "#1E4D8B", color: "white", height: "100vh" }}>
      <h3 style={{ padding: "10px" }}>MORGUE OFFLINE</h3>
      {menu.map((item, i) => (
        <div key={i} style={{ backgroundColor: colors[i], padding: "12px", margin: "4px 0", cursor: "pointer" }}>
          {item}
        </div>
      ))}
    </div>
  );
}
