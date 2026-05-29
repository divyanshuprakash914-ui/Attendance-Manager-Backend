from google import genai
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_solution_with_gemini(question_title: str, question_text: str, test_cases: list[str]):
    prompt = f"""
You are an expert programming assignment assistant.

Your job is to generate a correct DRAFT solution for the given assignment.
This is for learning and manual review. Do not include anything about auto-submission.

Return ONLY valid JSON.
Do not include markdown.
Do not include ``` fences.
Do not include explanation outside JSON.

JSON format must be exactly:
{{
  "detected_language": "string",
  "detected_framework": "string or null",
  "solution_code": "string",
  "explanation": ["string"],
  "assumptions": ["string"],
  "test_case_strategy": ["string"]
}}

Important rules:
1. Read the question text carefully.
2. Read the test cases carefully.
3. Generate code that satisfies the test cases exactly.
4. Do not add extra UI, text, labels, ids, classes, or behavior unless required.
5. Preserve exact button text, heading text, function names, input/output format, and variable behavior when specified.
6. If the question is React, use beginner-friendly React with function App() and export default App.
7. If the question is plain JavaScript, return only the required JavaScript code.
8. If the question is Python, return only the required Python code.
9. If the question is Java/C++/C, return a complete compilable solution.
10. If input/output format is provided, follow it exactly.
11. If HTML/CSS/JS is required, include only the necessary files/code in solution_code.
12. If the platform likely expects one file, return one complete file.
13. Do not use external libraries unless the question explicitly allows them.
14. Do not over-style the solution.
15. Do not include console logs unless needed for output.
16. Do not include comments inside solution_code unless useful and minimal.
17. Prefer simple, deterministic code over clever code.
18. If requirements are ambiguous, make the smallest assumption and mention it in assumptions.
19. explanation should explain the idea briefly.
20. test_case_strategy should explain how the code satisfies each visible test case.

For React-specific rules:
- Use useState only when state is needed.
- Store values in the exact format expected by the question/test cases.
- If color names are expected in lowercase, store lowercase values.
- Reset should return state to the exact default required by the question.
- Do not display placeholder values like "none" unless the question asks for it.
- Do not change required text.
- Keep button labels exactly the same as the question.

For DSA/problem-solving rules:
- Parse input exactly as specified.
- Print output exactly as specified.
- Handle edge cases.
- Include time and space complexity in explanation, not inside code unless asked.

Assignment metadata:

Question Title:
{question_title}

Question Text:
{question_text}

Visible Test Cases:
{test_cases}

Now generate the best possible draft solution.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    )

    return response.text