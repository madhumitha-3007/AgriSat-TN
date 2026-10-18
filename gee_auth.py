"""
Earth Engine Authentication and Initialization Module.
"""
import ee

PROJECT_ID = "formal-stratum-477808-j2"

def init_ee(project_id: str = PROJECT_ID) -> bool:
    """
    Initializes Earth Engine with the designated Cloud project.
    Falls back to interactive authentication if initial attempt fails.
    """
    try:
        ee.Initialize(project=project_id)
        print(f"[SUCCESS] Earth Engine initialized successfully with project: {project_id}")
        return True
    except Exception as e:
        print(f"[INFO] Initial ee.Initialize failed ({e}).")
        print("[ACTION REQUIRED] Earth Engine credentials not found or unauthenticated.")
        print(f"Please run 'earthengine authenticate' or run 'python gee_auth.py' interactively in your terminal.")
        try:
            ee.Authenticate()
            ee.Initialize(project=project_id)
            print(f"[SUCCESS] Earth Engine authenticated and initialized with project: {project_id}")
            return True
        except Exception as auth_err:
            print(f"[ERROR] Failed to complete Earth Engine authentication: {auth_err}")
            return False

if __name__ == "__main__":
    init_ee()
