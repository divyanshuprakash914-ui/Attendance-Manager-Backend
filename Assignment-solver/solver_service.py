def generate_react_solution(question_title: str, question_text: str, test_cases: list[str]):
    title_lower = question_title.lower()
    text_lower = question_text.lower()

    if "favorite color" in title_lower or "favorite color" in text_lower:
        return {
            "solution_type": "React useState draft",
            "solution_code": """
import { useState } from "react";

function App() {
  const [color, setColor] = useState("");

  return (
    <div>
      <h1 style={{ backgroundColor: color }}>
        {color ? `My favorite color is ${color}!` : "My favorite color is !"}
      </h1>

      <button onClick={() => setColor("blue")}>Blue</button>
      <button onClick={() => setColor("green")}>Green</button>
      <button onClick={() => setColor("red")}>Red</button>
      <button onClick={() => setColor("")}>Reset</button>
    </div>
  );
}

export default App;
""".strip(),
            "explanation": [
                "useState stores the selected color.",
                "Blue, Green, and Red buttons update the color state.",
                "The h1 background color uses the current color value.",
                "The h1 text updates with the selected color in lowercase.",
                "Reset clears the color and returns the heading to default.",
            ],
        }

    return {
        "solution_type": "Unsupported question draft",
        "solution_code": "",
        "explanation": [
            "No matching solver template found for this question yet.",
            "Add a new rule in solver_service.py for this question type.",
        ],
    }