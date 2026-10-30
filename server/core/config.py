import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Core Paths ---
# The root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent

# Data directory
DATA_DIR = ROOT_DIR / "data"
USERS_DIR = DATA_DIR / "users"
ROOMS_FILE = DATA_DIR / "rooms.json"
INDEX_FILE = DATA_DIR / "index.json"
IMAGES_DIR = DATA_DIR / "images"

# Game Logic Prompts
PROMPTS_DIR = ROOT_DIR / "server" / "game_logic" / "prompts"
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system_prompt.txt"
EXAMPLES_FILE = PROMPTS_DIR / "examples.md"


# --- AI Inference Services (Tailscale) ---
# 1. Ollama (Text generation via Qwen)
QWEN_API_URL = os.getenv("QWEN_API_URL", "http://100.126.92.69:11434/api/generate")
QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", "qwen-text")
QWEN_TIMEOUT = float(os.getenv("QWEN_TIMEOUT", "120.0"))

# 2. ComfyUI (Image generation)
COMFYUI_SERVER_ADDRESS = os.getenv("COMFYUI_SERVER_ADDRESS", "mrskele.tail5c1221.ts.net")
COMFYUI_API_URL = os.getenv("COMFYUI_API_URL", f"https://{COMFYUI_SERVER_ADDRESS}")
COMFYUI_TIMEOUT = float(os.getenv("COMFYUI_TIMEOUT", "180.0"))
QWEN_IMAGE_MODEL = os.getenv("QWEN_IMAGE_MODEL", "qwen_image_2.1_turbo_Q4_K_M.gguf")
QWEN_WORKFLOW_FILE = ROOT_DIR / "qwen_api.json"

# --- Security ---
# For simplicity, we're not using a complex signing key, but this is where it would go.
SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_default_key_for_dev")
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "a_not_so_secret_salt_for_dev_passwords")

# --- Ensure directories exist ---
DATA_DIR.mkdir(exist_ok=True)
USERS_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)
