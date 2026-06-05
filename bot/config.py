import os
from dotenv import load_dotenv

load_dotenv()

# Essential Bot Settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SUPREME_ADMIN_ID = int(os.getenv("SUPREME_ADMIN_ID", "123456789"))
ADMINS = [SUPREME_ADMIN_ID]

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://neondb_owner:npg_IOpVU02LneTP@ep-small-wave-aphhdg2s-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)


