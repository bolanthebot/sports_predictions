import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import NBAGameFullPage from "./Pages/NBAGameFullPage";
import NBATeamFullPage from "./Pages/NBATeamFullPage";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/game/:gameId" element={<NBAGameFullPage />} />
        <Route path="/team/:teamId" element={<NBATeamFullPage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
