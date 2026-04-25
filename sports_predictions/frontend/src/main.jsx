import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import NBAGameFullPage from "./Pages/NBAGameFullPage.jsx";
import NBATeamFullPage from "./Pages/NBATeamFullPage.jsx";
import MLBGameFullPage from "./Pages/MLBGameFullPage.jsx";
import MLBTeamFullPage from "./Pages/MLBTeamFullPage.jsx";
import SportLanding from "./Pages/SportLanding.jsx";
import NBADailyGameGrid from "./Components/NBADailyGameGrid.jsx";
import MLBDailyGameGrid from "./Components/MLBDailyGameGrid.jsx";
import ReactDOM from "react-dom/client";
import Header from "./Components/Header.jsx";
import ScrollToTop from "./Components/ScrollToTop.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <div className="min-h-screen py-4 sm:py-6">
    <React.StrictMode>
      <BrowserRouter>
        <div className="app-shell">
          <ScrollToTop />
          <Header />
          <Routes>
            <Route path="/" element={<SportLanding />} />
            <Route path="/nba" element={<NBADailyGameGrid />} />
            <Route path="/nba/game/:gameId" element={<NBAGameFullPage />} />
            <Route path="/nba/team/:teamId" element={<NBATeamFullPage />} />
            <Route path="/mlb" element={<MLBDailyGameGrid />} />
            <Route path="/mlb/game/:gameId" element={<MLBGameFullPage />} />
            <Route path="/mlb/team/:teamId" element={<MLBTeamFullPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </React.StrictMode>
  </div>
);
