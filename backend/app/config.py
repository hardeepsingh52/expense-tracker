import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b"

llm_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ["NVIDIA_API_KEY"]
)
