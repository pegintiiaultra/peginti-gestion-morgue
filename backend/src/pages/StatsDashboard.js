import React, { useState, useEffect } from "react";
import axios from "axios";
import { Bar } from "react-chartjs-2";
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

export default function StatsDashboard() {
  const [stats, setStats] = useState({ total_entrees: 0, total_transferts: 0, total_sorties: 0, corps_restants: 0 });

  useEffect(() => {
    axios.get("http://localhost:3001/api/stats").then(res => setStats(res.data));
  }, []);

  const data = {
    labels: ["Entrées", "Transferts", "Sorties", "Corps Restants"],
    datasets: [
      {
        label: "Statistiques morgue",
        data: [stats.total_entrees, stats.total_transferts, stats.total_sorties, stats.corps_restants],
        backgroundColor: ["#1E4D8B", "#E67E22", "#A93226", "#27AE60"]
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
    <div style={{ flex: 1, padding: "20px" }}>
      <h2>Statistiques</h2>
      <Bar data={data} options={options} />
    </div>
  );
}
