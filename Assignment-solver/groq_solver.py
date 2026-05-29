import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


def generate_solution_with_groq(question_title: str, question_text: str, test_cases: list):
    client = Groq(
        api_key=os.getenv("GROQ_API_KEY")
    )

    prompt = f"""
You are a coding assignment solver.

Return ONLY valid JSON.
Do not use markdown.
Do not wrap code in triple backticks.

JSON format must be exactly:

{{
  "detected_language": "Python or JavaScript or React",
  "detected_framework": null,
  "solution_code": "final code only",
  "explanation": [],
  "assumptions": [],
  "test_case_strategy": []
}}

Question Title:
{question_title}

Question Details:
{question_text}

Test Cases:
{test_cases}

Important:
- For coding/DSA/function questions, return only the function/source code in solution_code.
- For React/Newton Box questions, return only final src/App.js code in solution_code.
- Do not include markdown.
- Do not include ``` code fences.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You generate correct programming solutions and always return valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content.strip()

    content = content.replace("```json", "").replace("```", "").strip()

    json.loads(content)

    return content