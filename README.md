# 🏀 NBA Predictions Project

A full-stack NBA game prediction platform that uses machine learning
models and live NBA data to generate game outcome predictions. The
project combines a **FastAPI + Python ML backend** with a **ReactJS Frontend** to deliver predictions through a clean web
interface.

🌐 **Live Site:** http://www.nba-predictions.org/

------------------------------------------------------------------------

## ✨ Features

-   📊 Machine learning powered NBA game predictions\
-   🔄 Live data integration using `nba_api`\
-   ⚡ FastAPI backend for high-performance prediction requests\
-   💻 Modern frontend UI for viewing predictions\
-   🧠 Models built using scikit-learn and XGBoost

------------------------------------------------------------------------

## 🛠 Tech Stack

### Backend

-   Python
-   FastAPI
-   Pandas
-   NumPy
-   Scikit-learn
-   XGBoost
-   nba_api

### Frontend

-   JavaScript / JSX
-   Reactjs

------------------------------------------------------------------------

## 🚀 Running Locally

### 1️⃣ Clone the Repository

``` bash
git clone https://github.com/bolanthebot/sports_predictions.git
cd sports_predictions
```

------------------------------------------------------------------------

### 2️⃣ Install Frontend Dependencies

``` bash
npm install
```

------------------------------------------------------------------------

### 3️⃣ Install Backend Dependencies

``` bash
pip install pandas numpy scikit-learn nba_api fastapi xgboost
```

------------------------------------------------------------------------

### 4️⃣ Run Backend Server

From:

    /sports_predictions/backend

Run:

``` bash
py -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

------------------------------------------------------------------------

### 5️⃣ Run Frontend

From:

    /sports_predictions

Run:

``` bash
npm run dev
```

------------------------------------------------------------------------

### 6️⃣ Open the App

Go to:

    http://localhost:5173/

------------------------------------------------------------------------

## 🧪 Model Info

The prediction models are trained using historical NBA game data and
engineered features such as:

-   Team performance metrics\
-   Recent game trends\
-   Player/team statistics\
-   Matchup history


