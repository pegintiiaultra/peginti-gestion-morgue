import React from "react";
import Sidebar from "./components/Sidebar";
import DepotPage from "./pages/DepotPage";
import StatsCombined from "./pages/StatsCombined";

export default function App() {
  return (
    <div style={{ display: "flex" }}>
      {/* Sidebar fixe à gauche */}
      <Sidebar />

      {/* Contenu principal */}
      <div style={{ flex: 1 }}>
        <DepotPage />
        <StatsCombined />
      </div>
    </div>
  );
}
