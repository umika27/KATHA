import os,sys
from pathlib import Path
import pytest

os.environ["DATABASE_URL"]="sqlite:////tmp/katha-test.db"
os.environ["SARVAM_ENABLED"]="false"
sys.path.insert(0,str(Path(__file__).parents[1]))

@pytest.fixture(autouse=True)
def configure_trusted_test_fixtures():
    from app.main import app, get_upload_security_context, UploadSecurityContext
    app.dependency_overrides[get_upload_security_context] = lambda: UploadSecurityContext(allow_trusted_auto_accept=True)
    yield
    app.dependency_overrides.pop(get_upload_security_context, None)
