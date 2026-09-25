import React, { useState, useEffect } from "react";
import axios from "axios";
import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";

ChartJS.register(ArcElement, Tooltip, Legend);

export default function StatsDonut() {
  const [stats, setStats] = useState({ total_entrees: 0, total_transferts: 0, total_sorties: 0, corps_restants: 0 });

  useEffect(() => {
    axios.get("http://localhost:3001/api/stats").then(res => setStats(res.data));
  }, []);

  const data = {
    labels: ["Entrées", "Transferts", "Sorties", "Corps Restants"],
    datasets: [
      {
        data: [stats.total_entrees, stats.total_transferts, stats.total_sorties, stats.corps_restants],
        backgroundColor: ["#1E4D8B", "#E67E22", "#A93226", "#27AE60"],
        hoverOffset: 10
      }
    ]
  };

  const options = {
    responsive: true,
    plugins: {
      legend: { position: "right" },
      title: { display: true, text: "Répartition des corps" }
    }
  };

  return (
    <div style={{ flex: 1, padding: "20px" }}>
      <h2>Répartition</h2>
      <Doughnut data={data} options={options} />
    </div>
  );
}
