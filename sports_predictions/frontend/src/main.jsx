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
  <div className="bg-slate-900 min-h-screen">
    <React.StrictMode>
      <BrowserRouter>
        <ScrollToTop />
        <Header />
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/game/:gameId" element={<NBAGameFullPage />} />
          <Route path="/team/:teamId" element={<NBATeamFullPage />} />
        </Routes>
      </BrowserRouter>
    </React.StrictMode>
  </div>
);
