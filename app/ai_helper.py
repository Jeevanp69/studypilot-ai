import json
import os
import re

from dotenv import load_dotenv
from google import genai
from pypdf import PdfReader

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured.")

client = genai.Client(api_key=GEMINI_API_KEY)


PROMPT_TEMPLATE = """
You are an AI study assistant.

Analyze the following study material and return ONLY valid JSON.

Required JSON structure:

{{
  "summary": "A clear 150-250 word summary of the material.",
  "flashcards": [
    {{
      "question": "Question",
      "answer": "Answer"
        }}
  ],
  "quiz": [
    {{
      "question": "Multiple choice question",
      "options": ["A", "B", "C", "D"],
      "answer": "A",
      "explanation": "Brief explanation"
        }}
    ]
}}

Rules:
- Create exactly 5 flashcards.
- Create exactly 5 multiple-choice questions.
- Each quiz question must have exactly 4 options.
- "answer" must contain the correct option text.
- Keep the content grounded only in the supplied study material.
- Do not invent facts.
- Do not return Markdown.
- Do not wrap the JSON in ```json or ``` blocks.

Study material:

{text}
"""


def extract_text_from_pdf(filepath: str) -> str:
    """Extract text from all pages of a PDF."""
    reader = PdfReader(filepath)

    pages = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    extracted_text = "\n".join(pages).strip()

    if not extracted_text:
        raise ValueError("No readable text was found in the PDF.")

    return extracted_text


def _clean_json_response(raw: str) -> str:
    """Remove accidental Markdown code fences from the model response."""
    cleaned = raw.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned.strip()


def _validate_result(data: dict) -> dict:
    """Validate the minimum structure required by StudyPilot."""
    if not isinstance(data, dict):
        raise ValueError("AI response is not a JSON object.")

    summary = data.get("summary")
    flashcards = data.get("flashcards")
    quiz = data.get("quiz")

    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("AI response contains an invalid summary.")

    if not isinstance(flashcards, list) or len(flashcards) != 5:
        raise ValueError("AI response must contain exactly 5 flashcards.")

    if not isinstance(quiz, list) or len(quiz) != 5:
        raise ValueError("AI response must contain exactly 5 quiz questions.")

    for card in flashcards:
        if not isinstance(card, dict):
            raise ValueError("Invalid flashcard format.")

        if not isinstance(card.get("question"), str):
            raise ValueError("Flashcard question is invalid.")

        if not isinstance(card.get("answer"), str):
            raise ValueError("Flashcard answer is invalid.")

    for question in quiz:
        if not isinstance(question, dict):
            raise ValueError("Invalid quiz question format.")

        if not isinstance(question.get("question"), str):
            raise ValueError("Quiz question is invalid.")

        options = question.get("options")

        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(
                "Each quiz question must contain exactly 4 options."
            )

        if not all(isinstance(option, str) for option in options):
            raise ValueError("Quiz options must be strings.")

        if not isinstance(question.get("answer"), str):
            raise ValueError("Quiz answer is invalid.")

        if question["answer"] not in options:
            raise ValueError(
                "Quiz answer must match one of the provided options."
            )

        if not isinstance(question.get("explanation"), str):
            raise ValueError("Quiz explanation is invalid.")

    return data


def generate_notes_from_text(text: str) -> dict:
    """
    Generate a summary, flashcards, and quiz from study material.
    """

    if not text or not text.strip():
        raise ValueError("No text was provided.")

    # Keep the existing project's practical input limit for now.
    truncated_text = text[:12000]

    prompt = PROMPT_TEMPLATE.format(text=truncated_text)

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=prompt,
    )

    raw = interaction.output_text.strip()

    if not raw:
        raise ValueError("Gemini returned an empty response.")

    cleaned = _clean_json_response(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned invalid JSON."
        ) from exc

    return _validate_result(data)