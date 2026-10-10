from dotenv import load_dotenv
import os
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="Reply with exactly: SentinelAgent Gemini connected."
)

print(interaction.output_text)