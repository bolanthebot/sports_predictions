#!/usr/bin/env python3
"""Test the injury importance scoring system"""

from services.injury_features import get_player_importance_score, compute_team_injury_scores
from services.nba import get_rotation_players, get_all_games
import pandas as pd

print("=" * 60)
print("INJURY SYSTEM TEST")
print("=" * 60)

# Test 1: Get rotation players
print("\n[TEST 1] Fetching rotation players...")
rotation = get_rotation_players(min_minutes_avg=10)
print(f"Found {len(rotation)} rotation players\n")
print(rotation[["PLAYER_NAME", "MIN", "PTS"]].head(10))

# Test 2: Player importance scoring
print("\n\n[TEST 2] Player importance scoring examples:")
print("-" * 60)
for idx, row in rotation.head(10).iterrows():
    pid = int(row["PLAYER_ID"])
    pname = row["PLAYER_NAME"]
    mpg = float(row["MIN"])
    ppg = float(row["PTS"])
    importance = get_player_importance_score(pid, rotation)
    
    print(f"{pname:20s} | {mpg:5.1f} MPG | {ppg:5.1f} PPG | Importance: {importance:.2f}")

# Test 3: Compute team injury scores
print("\n\n[TEST 3] Computing team injury scores...")
df = get_all_games()
injuries_df = compute_team_injury_scores(df)
print(f"\nInjury features shape: {injuries_df.shape}")
print(injuries_df.head())

print("\n\n[TEST 4] Feature statistics:")
print(f"Mean injury_pts_lost: {injuries_df['injury_pts_lost'].mean():.2f}")
print(f"Mean injury_impact_score: {injuries_df['injury_impact_score'].mean():.2f}")
print(f"Max injury_impact_score: {injuries_df['injury_impact_score'].max():.2f}")
print(f"Teams with injuries: {(injuries_df['num_players_out'] > 0).sum()}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
