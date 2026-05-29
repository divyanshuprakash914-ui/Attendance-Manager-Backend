from solver_service import generate_react_solution

from fastapi import FastAPI
from api_client import PortalAPIClient
from pydantic import BaseModel

import time
import re
import json
import os

from urllib.parse import quote
import httpx


from gemini_solver import generate_solution_with_gemini
from groq_solver import generate_solution_with_groq
from submit_client import SubmitClient


import asyncio


# Request Models

class GenerateAndSubmitRequest(BaseModel):
    # This is assignment question hash, not playground hash
    question_hash: str
    language_id: int = 71
    confirm_submit: bool


class UpdateGitlabFileRequest(BaseModel):
    file_path: str = "src/App.js"
    content: str
    branch: str = "main"
    


class AssignmentURLRequest(BaseModel):
    url: str


# FastAPI App

app = FastAPI(
    title="Assignment Solver Assistant",
    description="Fetches assignments and helps analyze them safely.",
    version="1.0.0",
)


# In-memory mock DB
submission_store = {}


# Home / Test

@app.get("/")
def home():
    return {
        "status": "running",
        "message": "Assignment solver assistant backend running.",
    }


@app.get("/test-api")
async def test_api():
    client = PortalAPIClient()
    result = await client.get("/")
    return result


# Helper: Extract test cases

def extract_test_cases(q: dict):
    return [
        test.get("title", "")
        for mapping in q.get("assignment_question_project_playground_mappings", [])
        for test in mapping.get("test_cases", [])
    ]


# Helper: Fetch assignment details

async def fetch_assignment_details(course_hash: str, assignment_hash: str):
    client = PortalAPIClient()

    result = await client.get(
        f"/course/h/{course_hash}/assignment/h/{assignment_hash}/details/"
    )

    if not result["success"]:
        return result

    return {
        "success": True,
        "data": result["data"],
    }


# Helper: Assignment Question Hash -> Playground Hash

async def get_playground_hash(
    course_hash: str,
    assignment_hash: str,
    assignment_question_hash: str,
):

    client = PortalAPIClient()

    result = await client.get(
        f"/course/h/{course_hash}/assignment/h/{assignment_hash}/question/h/{assignment_question_hash}/details/"
    )

    if not result["success"]:
        return {
            "success": False,
            "message": "Could not fetch question detail / playground hash",
            "raw": result,
        }

    data = result["data"]

    playground_hash = data.get("hash")

    if not playground_hash:
        return {
            "success": False,
            "message": "Question detail response did not contain playground hash",
            "data": data,
        }

    return {
        "success": True,
        "assignment_question_hash": assignment_question_hash,
        "playground_hash": playground_hash,
        "data": data,
    }


# Helper: Get starter source code

async def get_playground_source_code(playground_hash: str):

    client = PortalAPIClient()

    result = await client.get(
        f"/playground/coding/h/{playground_hash}/"
    )

    if not result["success"]:
        return {
            "success": False,
            "message": "Could not fetch playground source code",
            "raw": result,
        }

    data = result["data"]

    return {
        "success": True,
        "playground_hash": playground_hash,
        "source_code": data.get("source_code", ""),
        "data": data,
    }


#Helper: Detect Playground Type:
def detect_playground_kind(playground_data: dict):
    playground_type = str(playground_data.get("type", "")).lower()
    sub_type_text = str(playground_data.get("sub_type_text", "")).lower()

    print("DEBUG playground_type:", playground_type)
    print("DEBUG sub_type_text:", sub_type_text)

    if playground_type == "code":
        return "coding"

    if playground_type == "newton-box":
        return "project"

    if "newton box" in sub_type_text:
        return "project"

    return "coding"

async def get_project_metadata(playground_hash: str):
    client = PortalAPIClient()

    result = await client.get(
        f"/playground/project/h/{playground_hash}/"
    )

    if not result["success"]:
        return result

    return {
        "success": True,
        "data": result["data"],
    }


async def get_gitlab_file_content(
    gitlab_project_id: int,
    access_token: str,
    file_path: str = "src/App.js",
):
    encoded_file_path = quote(file_path, safe="")
    branches = ["main", "master"]

    for branch in branches:
        url = (
            f"https://gitlab.newtonschool.co/api/v4/projects/"
            f"{gitlab_project_id}/repository/files/"
            f"{encoded_file_path}/raw?ref={branch}"
        )

        headers = {
            "PRIVATE-TOKEN": access_token,
        }

        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.get(url, headers=headers)

        if response.status_code == 200:
            return {
                "success": True,
                "file_path": file_path,
                "branch": branch,
                "content": response.text,
            }

    return {
        "success": False,
        "message": "Could not fetch GitLab file from main or master",
        "file_path": file_path,
    }


async def update_gitlab_file_content(
    gitlab_project_id: int,
    access_token: str,
    content: str,
    file_path: str = "src/App.js",
    branch: str = "main",
):
    encoded_file_path = quote(file_path, safe="")

    url = (
        f"https://gitlab.newtonschool.co/api/v4/projects/"
        f"{gitlab_project_id}/repository/files/"
        f"{encoded_file_path}"
    )

    headers = {
        "PRIVATE-TOKEN": access_token,
        "Content-Type": "application/json",
    }

    payload = {
        "branch": branch,
        "content": content,
        "commit_message": f"Update {file_path} from assignment solver",
    }

    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.put(url, json=payload, headers=headers)

    try:
        data = response.json()
    except Exception:
        data = response.text

    return {
        "success": response.status_code in [200, 201],
        "status_code": response.status_code,
        "data": data,
    }




# Assignment Detail

@app.get("/assignment-detail")
async def get_assignment_detail():
    client = PortalAPIClient()

    result = await client.get(
        "/course/h/ba5zr8ljtuei/assignment/h/px8ls5zw2jej/details/"
    )

    return result


# Assignment Summary

@app.get("/assignment-summary/{course_hash}/{assignment_hash}")
async def get_assignment_summary(course_hash: str, assignment_hash: str):
    result = await fetch_assignment_details(course_hash, assignment_hash)

    if not result["success"]:
        return result

    data = result["data"]
    assignment = data["assignment"]
    questions = assignment["assignment_questions"]

    clean_questions = []

    for q in questions:
        clean_questions.append({
            "question_hash": q.get("hash"),
            "title": q.get("question_title"),
            "slug": q.get("slug"),
            "type": q.get("question_type_text"),
            "max_marks": q.get("max_marks"),
            "difficulty": q.get("difficulty_type"),
            "test_cases_count": q.get("test_cases_count"),
            "question_text": q.get("question_text"),
            "earned_points": q.get("earnable_points", {}).get("earned_points"),
            "test_cases": extract_test_cases(q),
        })

    return {
        "success": True,
        "assignment_hash": assignment.get("hash"),
        "assignment_title": assignment.get("title"),
        "course_hash": assignment.get("course", {}).get("hash"),
        "course_title": assignment.get("course", {}).get("title"),
        "total_questions": assignment.get("total_questions"),
        "max_marks": assignment.get("max_marks"),
        "completed": data.get("completed"),
        "marks": data.get("marks"),
        "questions": clean_questions,
    }


# First Assignment Question

@app.get("/assignment-question/{course_hash}/{assignment_hash}")
async def get_assignment_question(course_hash: str, assignment_hash: str):
    result = await fetch_assignment_details(course_hash, assignment_hash)

    if not result["success"]:
        return result

    data = result["data"]
    assignment = data["assignment"]
    questions = assignment["assignment_questions"]

    if not questions:
        return {
            "success": False,
            "message": "No questions found in this assignment",
        }

    q = questions[0]

    return {
        "success": True,
        "assignment": {
            "hash": assignment.get("hash"),
            "title": assignment.get("title"),
            "course_hash": assignment.get("course", {}).get("hash"),
            "course_title": assignment.get("course", {}).get("title"),
        },
        "question": {
            "hash": q.get("hash"),
            "title": q.get("question_title"),
            "slug": q.get("slug"),
            "type": q.get("question_type_text"),
            "max_marks": q.get("max_marks"),
            "difficulty": q.get("difficulty_type"),
            "question_text": q.get("question_text"),
            "input": q.get("input"),
            "output": q.get("output"),
            "example": q.get("example"),
            "function_code": q.get("function_code"),
            "test_cases_count": q.get("test_cases_count"),
            "test_cases": extract_test_cases(q),
        },
    }


# Debug: Convert Question Hash to Playground Hash

@app.get("/question-playground-hash/{course_hash}/{assignment_hash}/{question_hash}")
async def question_to_playground_hash(
    course_hash: str,
    assignment_hash: str,
    question_hash: str, 
):
    return await get_playground_hash(
        course_hash=course_hash,
        assignment_hash=assignment_hash,
        assignment_question_hash=question_hash,
    )


# Debug: Fetch Playground Source

@app.get("/playground-source/{playground_hash}")
async def playground_source(playground_hash: str):
    return await get_playground_source_code(playground_hash)


# Safe Solution Draft

@app.get("/solve-draft/{course_hash}/{assignment_hash}")
async def get_solution_draft(course_hash: str, assignment_hash: str):
    result = await fetch_assignment_details(course_hash, assignment_hash)

    if not result["success"]:
        return result

    data = result["data"]
    assignment = data["assignment"]
    questions = assignment["assignment_questions"]

    if not questions:
        return {
            "success": False,
            "message": "No questions found in this assignment",
        }

    q = questions[0]
    test_cases = extract_test_cases(q)

    solution = generate_react_solution(
        question_title=q.get("question_title", ""),
        question_text=q.get("question_text", ""),
        test_cases=test_cases,
    )

    return {
        "success": True,
        "assignment_title": assignment.get("title"),
        "question_title": q.get("question_title"),
        "question_hash": q.get("hash"),
        "test_cases": test_cases,
        "solution_type": solution["solution_type"],
        "solution_code": solution["solution_code"],
        "explanation": solution["explanation"],
        "submit_status": "not_submitted",
    }


# Solve from URL

@app.post("/solve-from-url")
async def solve_from_url(req: AssignmentURLRequest):
    pattern = r"/course/([^/]+)/assignment/([^/]+)"
    match = re.search(pattern, req.url)

    if not match:
        return {
            "success": False,
            "message": "Invalid assignment URL. Expected format: /course/{course_hash}/assignment/{assignment_hash}",
        }

    course_hash = match.group(1)
    assignment_hash = match.group(2)

    return await solve_with_ai(course_hash, assignment_hash)


# Solve with Gemini AI

# @app.get("/solve-ai/{course_hash}/{assignment_hash}")

async def solve_question_with_ai(
    course_hash: str,
    assignment_hash: str,
    target_question_hash: str,
):
    result = await fetch_assignment_details(course_hash, assignment_hash)

    if not result["success"]:
        return result

    data = result["data"]
    assignment = data["assignment"]
    questions = assignment["assignment_questions"]

    if not questions:
        return {
            "success": False,
            "message": "No questions found in this assignment",
        }

    q = None

    for question in questions:
        if question.get("hash") == target_question_hash:
            q = question
            break

    if not q:
        return {
            "success": False,
            "message": "Question hash not found in assignment",
            "given_question_hash": target_question_hash,
        }

    assignment_question_hash = q.get("hash")
    test_cases = extract_test_cases(q)

    playground_result = await get_playground_hash(
        course_hash=course_hash,
        assignment_hash=assignment_hash,
        assignment_question_hash=assignment_question_hash,
    )

    if not playground_result["success"]:
        return playground_result

    playground_hash = playground_result["playground_hash"]
    playground_data = playground_result.get("data", {})
    playground_kind = detect_playground_kind(playground_data)

    print("DEBUG playground_kind:", playground_kind)
    print("DEBUG playground_hash:", playground_hash)

    starter_code = ""
    gitlab_project_id = None
    gitlab_access_token = None
    gitlab_file_path = None
    gitlab_branch = None

    actual_language_id = None
    actual_language_text = None

    if playground_kind == "coding":
        source_result = await get_playground_source_code(playground_hash)

        if source_result["success"]:
            starter_code = source_result.get("source_code", "")

            source_data = source_result.get("data", {})
            actual_language_id = source_data.get("language_id")
            actual_language_text = source_data.get("language_text")



    else:
        project_result = await get_project_metadata(playground_hash)

        if not project_result["success"]:
            return project_result

        project_data = project_result["data"]

        gitlab_project_id = project_data.get("git_lab_project_id")
        gitlab_access_token = project_data.get("access_token")
        gitlab_file_path = "src/App.js"

        if gitlab_project_id and gitlab_access_token:
            file_result = await get_gitlab_file_content(
                gitlab_project_id=gitlab_project_id,
                access_token=gitlab_access_token,
                file_path=gitlab_file_path,
            )

            if file_result["success"]:
                starter_code = file_result["content"]
                gitlab_branch = file_result["branch"]

    enhanced_question_text = f"""
            QUESTION TYPE:
            {q.get("question_type_text", "")}

            PLAYGROUND KIND:
            {playground_kind}

            QUESTION TEXT:
            {q.get("question_text", "")}

            INPUT:
            {q.get("input", "")}

            OUTPUT:
            {q.get("output", "")}

            EXAMPLE:
            {q.get("example", "")}

            FUNCTION CODE:
            {q.get("function_code", "")}

            STARTER CODE:
            {starter_code}

            IMPORTANT:
            If this is a React/Newton Box/project question, return only the final src/App.js code.
            If this is a coding/DSA question, return only the final source code.
        """
    try:
        # First try Gemini
        ai_text = generate_solution_with_gemini(
            question_title=q.get("question_title", ""),
            question_text=enhanced_question_text,
            test_cases=test_cases,
        )

        ai_provider = "gemini"

    except Exception as gemini_error:
        gemini_error_text = str(gemini_error)

        print("Gemini failed:", gemini_error_text)
        print("Trying Groq fallback...")

    try:
        # Fallback to Groq
        ai_text = generate_solution_with_groq(
            question_title=q.get("question_title", ""),
            question_text=enhanced_question_text,
            test_cases=test_cases,
        )

        ai_provider = "groq"

    except Exception as groq_error:
        return {
            "success": False,
            "message": "AI generation failed from both Gemini and Groq",
            "gemini_error": gemini_error_text,
            "groq_error": str(groq_error),
            "question_title": q.get("question_title"),
            "assignment_question_hash": assignment_question_hash,
            "playground_hash": playground_hash,
            "playground_kind": playground_kind,
            "actual_language_id": actual_language_id,
            "actual_language_text": actual_language_text,
        }

    try:
        ai_result = json.loads(ai_text)
    except Exception:
        return {
            "success": False,
            "message": "Gemini did not return valid JSON",
            "raw_response": ai_text,
        }

    return {
        "success": True,
        "assignment_title": assignment.get("title"),
        "ai_provider": ai_provider,
        "actual_language_id": actual_language_id,
        "actual_language_text": actual_language_text,
        "question_title": q.get("question_title"),
        "assignment_question_hash": assignment_question_hash,
        "playground_hash": playground_hash,
        "playground_kind": playground_kind,
        "starter_code_found": bool(starter_code),
        "gitlab_project_id": gitlab_project_id,
        "gitlab_access_token": gitlab_access_token,
        "gitlab_file_path": gitlab_file_path,
        "gitlab_branch": gitlab_branch,
        "test_cases": test_cases,
        "solution_type": "Gemini AI draft",
        "detected_language": ai_result.get("detected_language"),
        "detected_framework": ai_result.get("detected_framework"),
        "solution_code": ai_result.get("solution_code", ""),
        "explanation": ai_result.get("explanation", []),
        "assumptions": ai_result.get("assumptions", []),
        "test_case_strategy": ai_result.get("test_case_strategy", []),
        "submit_status": "not_submitted",
    }


@app.get("/solve-ai/{course_hash}/{assignment_hash}")

async def solve_with_ai(course_hash: str, assignment_hash: str):

    result = await fetch_assignment_details(course_hash, assignment_hash)

    if not result["success"]:
        return result

    data = result["data"]
    assignment = data["assignment"]
    questions = assignment["assignment_questions"]

    if not questions:
        return {
            "success": False,
            "message": "No questions found in this assignment",
        }

    first_question_hash = questions[0].get("hash")

    return await solve_question_with_ai(
        course_hash=course_hash,
        assignment_hash=assignment_hash,
        target_question_hash=first_question_hash,
    )

# Mock Submit Receiver

@app.patch("/playground/coding/h/{playground_hash}/run_hidden_test_cases=true")
async def mock_submit_api(playground_hash: str, payload: dict):
    submission_store[playground_hash] = {
        "hash": payload.get("hash"),
        "language_id": payload.get("language_id"),
        "source_code": payload.get("source_code", ""),
        "run_hidden_test": payload.get("run_hidden_test"),
        "showSubmissionTab": payload.get("showSubmissionTab"),
        "standard_input": payload.get("standard_input"),
    }

    return {
        "success": True,
        "message": "Mock submit saved successfully",
        "playground_hash": playground_hash,
        "saved": {
            "hash": payload.get("hash"),
            "language_id": payload.get("language_id"),
            "run_hidden_test": payload.get("run_hidden_test"),
            "showSubmissionTab": payload.get("showSubmissionTab"),
            "source_code_length": len(payload.get("source_code", "")),
        },
    }


@app.get("/mock-submission/{playground_hash}")
async def get_mock_submission(playground_hash: str):
    submission = submission_store.get(playground_hash)

    if not submission:
        return {
            "success": False,
            "message": "No submission found for this playground hash",
        }

    return {
        "success": True,
        "playground_hash": playground_hash,
        "submission": submission,
    }


# Prepare Submit Payload

@app.post("/generate-and-submit/{course_hash}/{assignment_hash}")
async def generate_and_submit(
    course_hash: str,
    assignment_hash: str,
    req: GenerateAndSubmitRequest,
):
    if not req.confirm_submit:
        return {
            "success": False,
            "message": "Submit blocked. confirm_submit must be true.",
        }

    ai_result = await solve_question_with_ai(
        course_hash=course_hash,
        assignment_hash=assignment_hash,
        target_question_hash=req.question_hash,
    )

    if not ai_result["success"]:
        return ai_result

    source_code = ai_result.get("solution_code", "")
    assignment_question_hash = ai_result.get("assignment_question_hash")
    playground_hash = ai_result.get("playground_hash")
    playground_kind = ai_result.get("playground_kind", "coding")

    if not source_code:
        return {
            "success": False,
            "message": "AI returned empty source_code. Submit stopped.",
        }

    if not playground_hash:
        return {
            "success": False,
            "message": "Could not get playground hash. Submit stopped.",
            "assignment_question_hash": assignment_question_hash,
        }

    if playground_kind == "coding":
        final_language_id = (
            ai_result.get("actual_language_id")
            or req.language_id
            or 71
        )
        submit_payload = {
            "hash": playground_hash,
            "standard_input": "",
            "source_code": source_code,
            "language_id": final_language_id,
            "run_hidden_test": True,
            "showSubmissionTab": True,
            "autoSave": False,
            "autosave": False,
            "isAttempt": False,
            "isAIAssignment": False,
            "is_force_save": True,
            "last_saved_at": int(time.time() * 1000),
        }

        submit_client = SubmitClient()

        result = await submit_client.patch(
            f"/playground/coding/h/{playground_hash}/?run_hidden_test_cases=true",
            submit_payload,
        )

        return {
            "success": result["success"],
            "message": "Generated AI code and sent to coding playground",
            "course_hash": course_hash,
            "assignment_hash": assignment_hash,
            "assignment_question_hash": assignment_question_hash,
            "playground_hash": playground_hash,
            "playground_kind": playground_kind,
            "question_title": ai_result.get("question_title"),
            "solution_type": "Coding solution submitted",
            "submit_payload_preview": {
                "hash": submit_payload["hash"],
                "language_id": submit_payload["language_id"],
                "actual_language_id": ai_result.get("actual_language_id"),
                "actual_language_text": ai_result.get("actual_language_text"),
                "source_code_length": len(source_code),
            },
            "submit_api_response": result,
        }

    if playground_kind == "project":
        gitlab_project_id = ai_result.get("gitlab_project_id")
        gitlab_access_token = ai_result.get("gitlab_access_token")
        gitlab_file_path = ai_result.get("gitlab_file_path") or "src/App.js"
        gitlab_branch = ai_result.get("gitlab_branch") or "main"

        if not gitlab_project_id or not gitlab_access_token:
            return {
                "success": False,
                "message": "GitLab project id or access token missing. Cannot update React file.",
                "playground_hash": playground_hash,
            }

        update_result = await update_gitlab_file_content(
            gitlab_project_id=gitlab_project_id,
            access_token=gitlab_access_token,
            content=source_code,
            file_path=gitlab_file_path,
            branch=gitlab_branch,
        )

        if not update_result["success"]:
            return {
                "success": False,
                "message": "React file update failed",
                "playground_hash": playground_hash,
                "updated_file": gitlab_file_path,
                "gitlab_update_response": update_result,
            }

        project_submit_payload = {
            "hash": playground_hash,
            "run_hidden_test": True,
            "showSubmissionTab": True,
            "autoSave": False,
            "autosave": False,
            "isAttempt": False,
            "isAIAssignment": False,
            "is_force_save": True,
            "last_saved_at": int(time.time() * 1000),
        }

        submit_client = SubmitClient()

        project_submit_result = await submit_client.patch(
            f"/playground/project/h/{playground_hash}/?run_hidden_test_cases=true",
            project_submit_payload,
        )

        return {
            "success": update_result["success"] and project_submit_result["success"],
            "message": "Generated AI React code and updated project file and auto submit file.",
            "course_hash": course_hash,
            "assignment_hash": assignment_hash,
            "assignment_question_hash": assignment_question_hash,
            "playground_hash": playground_hash,
            "playground_kind": playground_kind,
            "question_title": ai_result.get("question_title"),
            "solution_type": "React project file updated",
            "updated_file": gitlab_file_path,
            "branch": gitlab_branch,
            "source_code_length": len(source_code),
            "gitlab_update_response": update_result,
            "project_submit_response": project_submit_result,

        }

    return {
        "success": False,
        "message": f"Unsupported playground kind: {playground_kind}",
    }


#Submit As A Whole

@app.post("/generate-and-submit-all/{course_hash}/{assignment_hash}")
async def generate_and_submit_all(
    course_hash:str,
    assignment_hash:str,
    confirm_submit: bool = False,
):
    if not confirm_submit:
        return {
            "success":False,
            "message":"Submit Blocked. Set confirm_submit=true in query params. "
        }
    
    result = await fetch_assignment_details(course_hash, assignment_hash)

    if not result["success"]:
        return result
    
    data = result["data"]
    assignment = data["assignment"]
    questions = assignment["assignment_questions"]

    if not questions:
        return {
            "success":False,
            "message":"NO question found in assignment"
        }
    

    final_results = []

    for q in questions:
        question_hash = q.get("hash")
        question_title = q.get("question_title")

        req = GenerateAndSubmitRequest(
            question_hash=question_hash,
            language_id=0,
            confirm_submit=True,
        )

        submit_result = await generate_and_submit(
            course_hash=course_hash,
            assignment_hash=assignment_hash,
            req=req,
        )
        await asyncio.sleep(40)

        final_results.append({
                "question_title": question_title,
                "question_hash": question_hash,
                "success": submit_result.get("success"),
                "playground_hash": submit_result.get("playground_hash"),
                "playground_kind": submit_result.get("playground_kind"),

                "submit_status_code": (
                    submit_result.get("submit_api_response", {}).get("status_code")
                    or submit_result.get("project_submit_response", {}).get("status_code")
                ),

                "message": submit_result.get("message"),
                "error": submit_result.get("error"),

                "submit_payload_preview": submit_result.get("submit_payload_preview"),

                "submit_api_data_preview": str(
                    submit_result.get("submit_api_response", {}).get("data")
                    or submit_result.get("project_submit_response", {}).get("data")
                )[:1000],
        })

    return {
        "success": True,
        "assignment_title":assignment.get("title"),
        "course_hash":course_hash,
        "assignment_hash":assignment_hash,
        "total_questions":len(questions),
        "results":final_results,

    }


#Test react route(Which is working)
@app.get("/debug-playground-routes/{playground_hash}")
async def debug_playground_routes(playground_hash: str):
    client = PortalAPIClient()

    routes = [
        f"/playground/coding/h/{playground_hash}/",
        f"/playground/project/h/{playground_hash}/",
        f"/project-playground/h/{playground_hash}/",
        f"/playground/h/{playground_hash}/",
        f"/newton-box/h/{playground_hash}/",
        f"/playground/newton-box/h/{playground_hash}/",
    ]

    results = []

    for route in routes:
        result = await client.get(route)

        results.append({
            "route": route,
            "success": result.get("success"),
            "status_code": result.get("status_code"),
            "keys": list(result.get("data", {}).keys()) if isinstance(result.get("data"), dict) else None,
            "error": result.get("error") or result.get("data"),
        })

    return {
        "success": True,
        "playground_hash": playground_hash,
        "results": results,
    }



#React files route debug
# @app.get("/debug-project-file-routes/{playground_hash}")
# async def debug_project_file_routes(playground_hash: str):
#     client = PortalAPIClient()

#     routes = [
#         f"/playground/project/h/{playground_hash}/files/",
#         f"/playground/project/h/{playground_hash}/file/",
#         f"/playground/project/h/{playground_hash}/source/",
#         f"/playground/project/h/{playground_hash}/code/",
#         f"/playground/project/h/{playground_hash}/tree/",
#         f"/playground/project/h/{playground_hash}/file-tree/",
#         f"/playground/project/h/{playground_hash}/files?path=src/App.js",
#         f"/playground/project/h/{playground_hash}/file?path=src/App.js",
#         f"/playground/project/h/{playground_hash}/source?path=src/App.js",
#         f"/playground/project/h/{playground_hash}/code?path=src/App.js",
#     ]

#     results = []

#     for route in routes:
#         result = await client.get(route)

#         data = result.get("data")

#         results.append({
#             "route": route,
#             "success": result.get("success"),
#             "status_code": result.get("status_code"),
#             "keys": list(data.keys()) if isinstance(data, dict) else None,
#             "data_preview": str(data)[:500],
#             "error": result.get("error"),
#         })

#     return {
#         "success": True,
#         "playground_hash": playground_hash,
#         "results": results,
#     }


# from urllib.parse import quote
# import httpx


# @app.get("/debug-gitlab-file/{playground_hash}")
# async def debug_gitlab_file(playground_hash: str, file_path: str = "src/App.js"):
#     client = PortalAPIClient()

#     project_result = await client.get(
#         f"/playground/project/h/{playground_hash}/"
#     )

#     if not project_result["success"]:
#         return project_result

#     data = project_result["data"]

#     gitlab_project_id = data.get("git_lab_project_id")
#     access_token = data.get("access_token")

#     if not gitlab_project_id or not access_token:
#         return {
#             "success": False,
#             "message": "git_lab_project_id or access_token missing",
#         }

#     encoded_file_path = quote(file_path, safe="")

#     branches = ["main", "master"]

#     for branch in branches:
#         url = (
#             f"https://gitlab.newtonschool.co/api/v4/projects/"
#             f"{gitlab_project_id}/repository/files/"
#             f"{encoded_file_path}/raw?ref={branch}"
#         )

#         headers = {
#             "PRIVATE-TOKEN": access_token,
#         }

#         async with httpx.AsyncClient(timeout=30) as http:
#             response = await http.get(url, headers=headers)

#         if response.status_code == 200:
#             return {
#                 "success": True,
#                 "gitlab_project_id": gitlab_project_id,
#                 "file_path": file_path,
#                 "branch": branch,
#                 "content": response.text,
#             }

#     return {
#         "success": False,
#         "message": "Could not fetch file from main or master branch",
#         "file_path": file_path,
#     }


@app.get("/debug-project-submit-routes/{playground_hash}")
async def debug_project_submit_routes(playground_hash: str):
    submit_client = SubmitClient()

    payload = {
        "hash": playground_hash,
        "run_hidden_test": True,
        "showSubmissionTab": True,
        "autoSave": False,
        "autosave": False,
        "isAttempt": False,
        "isAIAssignment": False,
        "is_force_save": True,
        "last_saved_at": int(time.time() * 1000),
    }

    routes = [
        f"/playground/project/h/{playground_hash}/?run_hidden_test_cases=true",
        f"/playground/project/h/{playground_hash}/run_hidden_test_cases=true",
        f"/playground/project/h/{playground_hash}/submit/",
        f"/playground/project/h/{playground_hash}/run/",
        f"/playground/project/h/{playground_hash}/test/",
        f"/playground/project/h/{playground_hash}/evaluate/",
    ]

    results = []

    for route in routes:
        result = await submit_client.patch(route, payload)

        results.append({
            "route": route,
            "success": result.get("success"),
            "status_code": result.get("status_code"),
            "data_preview": str(result.get("data"))[:500],
        })

    return {
        "success": True,
        "playground_hash": playground_hash,
        "results": results,
    }



# Main.match(for react)
@app.put("/debug-update-gitlab-file/{playground_hash}")
async def debug_update_gitlab_file(
    playground_hash: str,
    req: UpdateGitlabFileRequest,
):
    client = PortalAPIClient()

    project_result = await client.get(
        f"/playground/project/h/{playground_hash}/"
    )

    if not project_result["success"]:
        return project_result

    data = project_result["data"]

    gitlab_project_id = data.get("git_lab_project_id")
    access_token = data.get("access_token")

    if not gitlab_project_id or not access_token:
        return {
            "success": False,
            "message": "git_lab_project_id or access_token missing",
        }

    encoded_file_path = quote(req.file_path, safe="")

    url = (
        f"https://gitlab.newtonschool.co/api/v4/projects/"
        f"{gitlab_project_id}/repository/files/"
        f"{encoded_file_path}"
    )

    headers = {
        "PRIVATE-TOKEN": access_token,
        "Content-Type": "application/json",
    }

    payload = {
        "branch": req.branch,
        "content": req.content,
        "commit_message": f"Update {req.file_path} from API",
    }

    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.put(url, json=payload, headers=headers)

    try:
        response_data = response.json()
    except Exception:
        response_data = response.text

    return {
        "success": response.status_code in [200, 201],
        "status_code": response.status_code,
        "file_path": req.file_path,
        "branch": req.branch,
        "data": response_data,
    }



