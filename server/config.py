"""配置加载 — 环境变量 + workspace文件路径"""

import os

# 加载 .env 文件
def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = val.strip()

_load_dotenv()

# 路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.join(BASE_DIR, "openclaw-workspace")
SKILLS_DIR = os.path.join(WORKSPACE_DIR, "skills")

# LLM
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")

# Server
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8010"))

# Mock API (self) — 始终用 127.0.0.1，因为子进程回调在同一容器内
MOCK_API_URL = f"http://127.0.0.1:{PORT}"


def load_workspace_file(filename: str) -> str:
    """加载workspace文件内容。"""
    path = os.path.join(WORKSPACE_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def load_skill_md(skill_name: str) -> str:
    """加载指定Skill的SKILL.md。"""
    path = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_skill_scripts_dir(skill_name: str) -> str:
    return os.path.join(SKILLS_DIR, skill_name, "scripts")
