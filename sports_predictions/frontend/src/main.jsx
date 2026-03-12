import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import NBAGameFullPage from "./Pages/NBAGameFullPage.jsx";
import NBATeamFullPage from "./Pages/NBATeamFullPage.jsx";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
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
            <Route path="/" element={<App />} />
            <Route path="/game/:gameId" element={<NBAGameFullPage />} />
            <Route path="/team/:teamId" element={<NBATeamFullPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </React.StrictMode>
  </div>
);
