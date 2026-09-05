import os,sys
from pathlib import Path
os.environ["DATABASE_URL"]="sqlite:////tmp/katha-test.db"
os.environ["SARVAM_ENABLED"]="false"
sys.path.insert(0,str(Path(__file__).parents[1]))
