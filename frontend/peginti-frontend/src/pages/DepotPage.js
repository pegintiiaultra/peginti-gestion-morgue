import React, { useState, useEffect } from "react";
import axios from "axios";

export default function DepotPage() {
  const [depots, setDepots] = useState([]);

  useEffect(() => {
    axios.get("http://localhost:3001/api/depot").then(res => setDepots(res.data));
  }, []);

  return (
    <div style={{ flex: 1, padding: "20px" }}>
      <h2>Dépôts Actifs</h2>
      <table border="1" cellPadding="6" style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th>N° Dépôt</th><th>Nom Défunt</th><th>Casier</th><th>Date Entrée</th><th>Statut</th>
          </tr>
        </thead>
        <tbody>
          {depots.map(d => (
            <tr key={d[0]}>
              <td>{d[1]}</td><td>{d[2]}</td><td>{d[5]}</td><td>{d[6]}</td>
              <td style={{ color: d[7] === "OK" ? "#27AE60" : "#E67E22" }}>{d[7]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
