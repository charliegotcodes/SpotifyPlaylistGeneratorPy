import os
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")

# Read/search client 
SUPABASE_ANON: Client = create_client(SUPABASE_URL, os.getenv("SUPABASE_KEY"))

# Write client (SERVER ONLY)
_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ADMIN: Optional[Client] = create_client(SUPABASE_URL, _service_key) if _service_key else None