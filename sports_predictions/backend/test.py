from nbainjuries import injury
from datetime import datetime

json_output = injury.get_reportdata(datetime(year=2026, month=1, day=13, hour=13, minute=30)) 
print(json_output)
#df_output = injury.get_reportdata(datetime(year=2025, month=4, day=25, hour=17, minute=30), return_df=True)