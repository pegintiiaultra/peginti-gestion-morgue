import React, { useState, useEffect } from "react";
import axios from "axios";
import { Bar, Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, ArcElement, Title, Tooltip, Legend } from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Title, Tooltip, Legend);

export default function StatsCombined() {
  const [stats, setStats] = useState({ total_entrees: 0, total_transferts: 0, total_sorties: 0, corps_restants: 0 });

  useEffect(() => {
    axios.get("http://localhost:3001/api/stats").then(res => setStats(res.data));
  }, []);

  const barData = {
    labels: ["Entrées", "Transferts", "Sorties", "Corps Restants"],
    datasets: [
      {
        label: "Statistiques morgue",
        data: [stats.total_entrees, stats.total_transferts, stats.total_sorties, stats.corps_restants],
        backgroundColor: ["#1E4D8B", "#E67E22", "#A93226", "#27AE60"]
      }
    ]
  };

  const pieData = {
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
      legend: { position: "top" },
      title: { display: true, text: "Tableau de bord morgue" }
    }
  };

  return (
    <div style={{ display: "flex", gap: "40px", padding: "20px" }}>
      <div style={{ flex: 1 }}>
        <h2>Statistiques (Barres)</h2>
        <Bar data={barData} options={options} />
      </div>
      <div style={{ flex: 1 }}>
        <h2>Répartition (Donut)</h2>
        <Doughnut data={pieData} options={options} />
      </div>
    </div>
  );
}
