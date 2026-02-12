from nbainjuries import injury
from datetime import datetime

json_output = injury.get_reportdata(datetime(year=2026, month=1, day=13, hour=13, minute=30)) 
print(json_output)
#df_output = injury.get_reportdata(datetime(year=2025, month=4, day=25, hour=17, minute=30), return_df=True)    
#Returns:
"""[
  {
    "Game Date":"01\/13\/2026",
    "Game Time":"07:30 (ET)",
    "Matchup":"PHX@MIA",
    "Team":"Phoenix Suns",
    "Player Name":"Bouyea, Jamaree",
    "Current Status":"Out",
    "Reason":"Concussion Protocol"
  },
  {
    "Game Date":"01\/13\/2026",
    "Game Time":"07:30 (ET)",
    "Matchup":"PHX@MIA",
    "Team":"Phoenix Suns",
    "Player Name":"Goodwin, Jordan",
    "Current Status":"Available",
    "Reason":"Injury\/Illness - Jaw; Sprain (Mask)"""