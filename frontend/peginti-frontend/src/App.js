import React from "react";
import Sidebar from "./components/Sidebar";
import DepotPage from "./pages/DepotPage";

export default function App() {
  return (
    <div style={{ display: "flex" }}>
      <Sidebar />
      <DepotPage />
    </div>
  );
}
