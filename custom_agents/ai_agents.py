import os
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel
from dotenv import load_dotenv

# Load key variables from .env file
load_dotenv()

# Disable agents runtime telemetry/logging to external services (if configured)


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL   = os.getenv("OPENROUTER_MODEL")
OPENROUTER_URL = os.getenv("OPENROUTER_URL")

# Create an asynchronous OpenAI client pointed at OpenRouter's proxy URL
external_client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_URL,
)

# Instantiate theOpenAIChatCompletionsModel utilizing the proxy client
model = OpenAIChatCompletionsModel(
    openai_client=external_client,
    model=OPENROUTER_MODEL
)


# --- System Instructions / Prompts for AI Agents ---

SCORER_INSTRUCTIONS = """
You are a professional resume screener with 10 years of recruiting experience.
Compare the candidate's resume against the job description and respond with ONLY valid JSON:

{
  "score": <integer 0-100>,
  "summary": "<one sentence overall assessment>",
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "improvements": ["<improvement 1>", "<improvement 2>", "<improvement 3>"],
  "missing_keywords": ["<keyword 1>", "<keyword 2>"]
}

Be specific. Name actual technologies and skills from both documents. No markdown, no extra text.
"""

COVER_LETTER_INSTRUCTIONS = """
You are an expert career coach who writes outstanding cover letters.
Write a 3-4 paragraph cover letter under 350 words, specific to the company and role.
Do not include placeholders like [Your Name] — just write the body directly.
When the user asks for revisions, refine accordingly.
"""

INTERVIEW_PREP_INSTRUCTIONS = """
You are an experienced technical interviewer and career coach.
Generate 6 interview questions for the role. Respond with ONLY valid JSON:

{
  "questions": [
    {
      "question": "<the interview question>",
      "type": "technical" | "behavioral" | "situational",
      "tip": "<one-sentence tip on how to answer well>"
    }
  ]
}

For follow-up messages like sample answers or extra questions, respond in plain text.
"""

# --- Agent Initializations ---

resume_scorer_agent = Agent(
    name="Resume Scorer",
    instructions=SCORER_INSTRUCTIONS,
    model=model,
)

cover_letter_agent = Agent(
    name="Cover Letter Generator",
    instructions=COVER_LETTER_INSTRUCTIONS,
    model=model,
)

interview_prep_agent = Agent(
    name="Interview Prep",
    instructions=INTERVIEW_PREP_INSTRUCTIONS,
    model=model,
)

# Registry map to look up instances by string key
AGENTS = {
    "scorer":          resume_scorer_agent,
    "cover_letter":    cover_letter_agent,
    "interview_prep":  interview_prep_agent,
}

async def run_agent_once(agent_type: str, user_message: str) -> str:
    """
    Runs an agent for a single input text block (non-interactive).
    Returns the string representing the LLM's final response.
    """
    agent = AGENTS.get(agent_type)
    if not agent:
        raise ValueError(f"Unknown agent type: {agent_type}")
    result = await Runner.run(agent, input=user_message)
    return result.final_output

async def run_agent_chat(agent_type: str, messages: list[dict]) -> str:
    """
    Runs an agent with full message history for interactive chats.
    Receives an array of dicts: [{'role': '...', 'content': '...'}]
    """
    agent = AGENTS.get(agent_type)
    if not agent:
        raise ValueError(f"Unknown agent type: {agent_type}")
    result = await Runner.run(agent, input=messages)
    return result.final_output
