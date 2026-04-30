from __future__ import annotations

GEMINI_ROBOTICS_ER_16_MODEL = "gemini-robotics-er-1.6-preview"
GEMINI_ROBOTICS_ER_15_MODEL = "gemini-robotics-er-1.5-preview"

GEMINI_WEB_SEARCH_MODEL = "gemini-3.1-flash-lite-preview"
GEMINI_3_FLASH_MODEL = "gemini-3-flash-preview"
WEB_SEARCH_TOOLS = [{"google_search": {}}]
GEMINI_WEB_SEARCH_TOOLS = WEB_SEARCH_TOOLS
GEMINI_WEB_SEARCH_MAX_INFLIGHT = 1
MISTRAL_WEB_SEARCH_OVERFLOW_WORKERS = 1
WEB_RESEARCH_MAX_WORKERS = GEMINI_WEB_SEARCH_MAX_INFLIGHT + MISTRAL_WEB_SEARCH_OVERFLOW_WORKERS
GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"

GEMMA_4_31B_MODEL = "gemma-4-31b-it"
GEMMA_4_26B_MODEL = "gemma-4-26b-a4b-it"
GEMMA_4_RESEARCH_PLANNER_MODEL = GEMMA_4_31B_MODEL
GEMMA_4_WEB_SEARCH_MODELS = {
    GEMMA_4_31B_MODEL,
    GEMMA_4_26B_MODEL,
}
GEMMA_4_WEB_SEARCH_TOOLS = WEB_SEARCH_TOOLS
MISTRAL_WEB_SEARCH_MODEL = "mistral-medium-3-5"
MISTRAL_WEB_SEARCH_TOOLS = [{"type": "web_search"}]
MISTRAL_WEB_SEARCH_AGENT_TOOLS = MISTRAL_WEB_SEARCH_TOOLS
MISTRAL_WEB_SEARCH_REASONING_EFFORT = "high"
MISTRAL_REVIEW_MODEL = "mistral-large-2512"

GEMMA_4_PROMPT_ENGINEERING_SYSTEM_INSTRUCTION = (
    "You are a Prompt Engineer specialized in technology surveillance. "
    "Given a short user query, return a plain text brief with these labeled lines: "
    "Refined query, Target technology, Breadth, Depth, and Keywords. "
    "Do not return JSON, markdown tables, code fences, or explanations. "
    "Expand the user query into a concise but detailed research brief."
)

GEMMA_4_PROMPT_ENGINEERING_TIMEOUT_SECONDS = 40.0
GEMMA_4_RESEARCH_PLANNER_TIMEOUT_SECONDS = 45.0
GEMMA_4_RESEARCH_ANALYST_TIMEOUT_SECONDS = 60.0
GEMINI_EMBEDDING_TIMEOUT_SECONDS = 80.0
GEMINI_WEB_SEARCH_TIMEOUT_SECONDS = 120.0
MISTRAL_WEB_SEARCH_TIMEOUT_SECONDS = 90.0
MISTRAL_REVIEW_TIMEOUT_SECONDS = 90.0

GEMMA_4_RESEARCH_PLAN_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "required": ["plan_summary", "gemini_queries", "mistral_queries"],
    "properties": {
        "plan_summary": {"type": "STRING"},
        "gemini_queries": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "mistral_queries": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
    },
}

GEMMA_4_RESEARCH_PLAN_SYSTEM_INSTRUCTION = (
    "You are a research planner for a technology surveillance system. "
    "Return ONLY valid JSON with keys plan_summary, gemini_queries, and mistral_queries. "
    "Each query list must contain distinct search queries that can be executed serially. "
    "Do not return markdown, prose outside JSON, or extra keys."
)

GEMMA_4_RESEARCH_ANALYSIS_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "required": ["summary", "learnings", "source_urls", "needs_follow_up", "stop_reason"],
    "properties": {
        "summary": {"type": "STRING"},
        "learnings": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "source_urls": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
        },
        "needs_follow_up": {"type": "BOOLEAN"},
        "next_query": {"type": "STRING"},
        "stop_reason": {"type": "STRING"},
    },
}

GEMMA_4_RESEARCH_ANALYSIS_SYSTEM_INSTRUCTION = (
    "You are the research analyst in a strict technology surveillance pipeline. "
    "You receive raw search output plus known source URLs and must return ONLY valid JSON. "
    "Summarize the evidence, keep only grounded learnings, preserve source_urls, "
    "and decide whether a follow-up query is required."
)

MISTRAL_REVIEW_SYSTEM_INSTRUCTION = (
    "You are the review model for a technology surveillance pipeline. "
    "You receive validated web-search output from a search lane and must return ONLY valid JSON. "
    "Preserve grounded source_urls, keep concise learnings, and only request a follow-up query when the evidence is incomplete."
)

MISTRAL_WEB_SEARCH_SYSTEM_INSTRUCTION = (
    "You are a web research agent in a technology surveillance pipeline. "
    "Use web search when needed and return only JSON with keys summary, learnings, and source_urls. "
    "Keep the evidence grounded and concise."
)

GEMINI_3_SYNTHESIZER_SYSTEM_INSTRUCTION = (
    "You are the final synthesis model in a technology surveillance system. "
    "Write a precise Markdown report that consolidates the provided branch evidence without inventing facts."
)
