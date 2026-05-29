import os
import math
import datetime
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)

BASE_URL = "https://my.newtonschool.co"
ALERT_THRESHOLD = float(os.getenv("ATTENDANCE_THRESHOLD", 77))

OVERALL_COURSE_HASH = "c6ootz3nd2y8"

COURSES = {
    "chemistry": {
        "label": "Applied Chem",
        "path": "/api/v2/course/h/x63irurahd7y/self_performance/",
    },
    "chemistry_lab": {
        "label": "Applied Chem Lab 2",
        "path": "/api/v2/course/h/w2cnsqrqs2wf/self_performance/",
    },
    "english": {
        "label": "English",
        "path": "/api/v2/course/h/zenm76zyjzil/self_performance/",
    },
    "math": {
        "label": "Prob. & Stat.",
        "path": "/api/v2/course/h/yulq4tu1cfrl/self_performance/",
    },
    "math_lab": {
        "label": "P&S Lab 2",
        "path": "/api/v2/course/h/nn8gcpgrlwja/self_performance/",
    },
    "dsa": {
        "label": "DSA",
        "path": "/api/v2/course/h/lpy9ubdndi3h/self_performance/",
    },
    "dsa_lab": {
        "label": "DSA Lab 2",
        "path": "/api/v2/course/h/d1ro0r1vpauy/self_performance/",
    },
    "wap": {
        "label": "WAP",
        "path": "/api/v2/course/h/ba5zr8ljtuei/self_performance/",
    },
    "wap_lab": {
        "label": "WAP Lab 2",
        "path": "/api/v2/course/h/zxlg4e35f37w/self_performance/",
    },
    "india_constitution": {
        "label": "India Constitution 2",
        "path": "/api/v2/course/h/yse2mx5tr8et/self_performance/",
    },
    "yoga": {
        "label": "Yoga",
        "path": "/api/v2/course/h/h3spjcl21sbo/self_performance/",
    },
}

GROUPS = {
    "Math + Math Lab": ["math", "math_lab"],
    "WAP + WAP Lab": ["wap", "wap_lab"],
    "Applied Chem + Lab": ["chemistry", "chemistry_lab"],
    "DSA + DSA Lab": ["dsa", "dsa_lab"],
    "Yoga": ["yoga"],
}

TIMETABLE = {
    "monday": [
        {"time": "09:00 AM", "key": "math"},
        {"time": "10:30 AM", "key": "dsa"},
        {"time": "01:30 PM", "key": "india_constitution"},
        {"time": "02:15 PM", "key": "chemistry_lab"},
        {"time": "03:45 PM", "key": "math_lab"},
    ],
    "tuesday": [
        {"time": "09:00 AM", "key": "chemistry"},
        {"time": "10:30 AM", "key": "dsa"},
        {"time": "01:30 PM", "key": "yoga"},
        {"time": "02:15 PM", "key": "wap_lab"},
        {"time": "03:45 PM", "key": "english"},
    ],
    "wednesday": [
        {"time": "09:00 AM", "key": "dsa"},
        {"time": "10:30 AM", "key": "math"},
        {"time": "01:30 PM", "key": "dsa_lab"},
        {"time": "03:00 PM", "key": "math_lab"},
        {"time": "04:30 PM", "key": "chemistry_lab"},
    ],
    "thursday": [
        {"time": "09:00 AM", "key": "dsa"},
        {"time": "10:30 AM", "key": "chemistry"},
        {"time": "01:30 PM", "key": "wap_lab"},
        {"time": "03:00 PM", "key": "yoga"},
        {"time": "04:30 PM", "key": "dsa_lab"},
    ],
    "friday": [
        {"time": "01:30 PM", "key": "yoga"},
    ],
}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]


def get_token():
    token = os.getenv("NEWTON_BEARER_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="NEWTON_BEARER_TOKEN missing in .env")
    return token


def get_headers():
    return {
        "Authorization": f"Bearer {get_token()}",
        "Accept": "application/json",
    }


def get_json(url):
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Newton API error: {response.text}"
            )

        return response.json()

    except requests.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to Newton API: {str(e)}"
        )


def calc_percentage(attended, total):
    if total == 0:
        return 0
    return round((attended / total) * 100, 2)


def classes_needed_to_reach(attended, total, target_percent):
    if total == 0:
        return 0

    current = calc_percentage(attended, total)

    if current >= target_percent:
        return 0

    target = target_percent / 100
    x = (target * total - attended) / (1 - target)
    return math.ceil(x)


def max_bunks_allowed(attended, total, target_percent):
    if total == 0:
        return 0

    current = calc_percentage(attended, total)

    if current < target_percent:
        return 0

    target = target_percent / 100
    x = (attended / target) - total
    return max(0, int(x))


def get_overall_attendance():
    url = f"{BASE_URL}/api/v2/course/h/{OVERALL_COURSE_HASH}/self_performance/"
    data = get_json(url)

    return {
        "attended": data.get("total_lectures_attended", 0),
        "total": data.get("total_lectures", 0),
    }


def get_subject_attendance(course_key):
    course = COURSES[course_key]
    url = BASE_URL + course["path"]
    data = get_json(url)

    attended = data.get("total_lectures_attended", 0)
    total = data.get("total_lectures", 0)

    percentage = calc_percentage(attended, total)

    return {
        "key": course_key,
        "name": course["label"],
        "attended": attended,
        "total": total,
        "percentage": percentage,
        "classes_needed": classes_needed_to_reach(attended, total, ALERT_THRESHOLD),
        "bunks_allowed": max_bunks_allowed(attended, total, ALERT_THRESHOLD),
        "status": "danger" if percentage < ALERT_THRESHOLD else "safe",
    }


def get_today_name():
    now = datetime.datetime.now()
    index = now.weekday()

    if index >= 5:
        return "monday"

    return WEEKDAYS[index]


def simulate_leave_for_day(day_name, overall):
    classes = TIMETABLE.get(day_name, [])
    missed = len(classes)

    new_total = overall["total"] + missed
    new_attended = overall["attended"]

    return {
        "day": day_name,
        "classes": missed,
        "attended": new_attended,
        "total": new_total,
        "percentage": calc_percentage(new_attended, new_total),
    }


def simulate_attend_all_for_day(day_name, overall):
    classes = TIMETABLE.get(day_name, [])
    count = len(classes)

    new_total = overall["total"] + count
    new_attended = overall["attended"] + count

    return {
        "attended": new_attended,
        "total": new_total,
        "percentage": calc_percentage(new_attended, new_total),
    }


def simulate_leave_one_class(day_name, overall):
    classes = TIMETABLE.get(day_name, [])
    count = len(classes)

    if count == 0:
        return {
            "attended": overall["attended"],
            "total": overall["total"],
            "percentage": calc_percentage(overall["attended"], overall["total"]),
        }

    new_total = overall["total"] + count
    new_attended = overall["attended"] + count - 1

    return {
        "attended": new_attended,
        "total": new_total,
        "percentage": calc_percentage(new_attended, new_total),
    }


@router.get("/overview")
def dashboard_overview():
    overall = get_overall_attendance()

    overall_percentage = calc_percentage(overall["attended"], overall["total"])

    subjects = []
    for key in COURSES:
        try:
            subjects.append(get_subject_attendance(key))
        except Exception:
            continue

    groups = []

    for group_name, course_keys in GROUPS.items():
        total = 0
        attended = 0

        for key in course_keys:
            subject = next((s for s in subjects if s["key"] == key), None)

            if subject:
                total += subject["total"]
                attended += subject["attended"]

        groups.append({
            "name": group_name,
            "attended": attended,
            "total": total,
            "percentage": calc_percentage(attended, total),
        })

    low_subjects = [
        s for s in subjects if s["percentage"] < ALERT_THRESHOLD
    ]

    low_subjects = sorted(low_subjects, key=lambda x: x["percentage"])

    today = get_today_name()

    today_classes = []

    for item in TIMETABLE.get(today, []):
        key = item["key"]
        subject = next((s for s in subjects if s["key"] == key), None)

        if not subject:
            continue

        if subject["percentage"] < ALERT_THRESHOLD:
            action = "must_attend"
        else:
            action = "safe"

        today_classes.append({
            "time": item["time"],
            "key": key,
            "subject": subject["name"],
            "percentage": subject["percentage"],
            "action": action,
            "status": "upcoming",
        })

    leave_days = []
    current_percentage = overall_percentage

    for day in WEEKDAYS:
        sim = simulate_leave_for_day(day, overall)
        change = round(sim["percentage"] - current_percentage, 2)

        if sim["percentage"] >= ALERT_THRESHOLD:
            risk = "safe"
        elif sim["percentage"] >= ALERT_THRESHOLD - 2:
            risk = "medium"
        else:
            risk = "high"

        leave_days.append({
            "day": day.capitalize(),
            "classes": sim["classes"],
            "if_absent_percentage": sim["percentage"],
            "change": change,
            "risk": risk,
        })

    best_day = max(leave_days, key=lambda x: x["if_absent_percentage"])

    attend_all = simulate_attend_all_for_day(today, overall)
    leave_one = simulate_leave_one_class(today, overall)

    return {
        "user": {
            "name": "Vani",
            "role": "Student",
        },
        "kpis": {
            "overall_percentage": overall_percentage,
            "attended": overall["attended"],
            "total": overall["total"],
            "classes_needed": classes_needed_to_reach(
                overall["attended"],
                overall["total"],
                ALERT_THRESHOLD,
            ),
            "bunks_allowed": max_bunks_allowed(
                overall["attended"],
                overall["total"],
                ALERT_THRESHOLD,
            ),
            "threshold": ALERT_THRESHOLD,
        },
        "subjects": subjects,
        "groups": groups,
        "low_subjects": low_subjects,
        "today_classes": {
            "day": today,
            "classes": today_classes,
        },
        "bunk_planner": {
            "best_day": best_day["day"],
            "days": leave_days,
        },
        "one_class_leave": {
            "day": today,
            "attend_all": attend_all,
            "leave_one": leave_one,
        },
        "assignments": {
            "completed": 0,
            "total": 0,
            "subjects": [],
        },
    }