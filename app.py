import os
from typing import List

from flask import Flask, request, render_template_string
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

app = Flask(__name__)

TOPICS = [
    "Verilog",
    "8051",
    "Digital Electronics",
    "VLSI",
    "Python",
    "Communication"
]

LEVELS = ["Beginner", "Intermediate", "Advanced"]

LEVEL_TO_NUM = {
    "Beginner": 1,
    "Intermediate": 2,
    "Advanced": 3
}

NUM_TO_LEVEL = {
    1: "Beginner",
    2: "Intermediate",
    3: "Advanced"
}

OPTION_LETTERS = ["A", "B", "C", "D"]
MODEL_NAME = "gemini-3.6-flash"


class VivaQuestion(BaseModel):
    question: str
    options: List[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str
    concept: str
    difficulty: int = Field(ge=1, le=3)


class VivaQuestionSet(BaseModel):
    questions: List[VivaQuestion]


question_prompt = ChatPromptTemplate.from_template("""
You are a strict engineering and computer science viva examiner.

Topic:
{topic}

Generate exactly 15 multiple-choice viva questions:
5 Beginner, 5 Intermediate, 5 Advanced.

Rules:
- Every question MUST be about {topic}.
- Do not include unrelated subjects.
- Each question must have exactly 4 options.
- Only ONE option must be correct.
- Give a short explanation.
- Give a short concept name.
- Mark difficulty correctly.
- Do not repeat questions.

Return only the structured question set.
""")


def get_llm():
    api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not configured in Render."
        )

    return ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        google_api_key=api_key,
        temperature=0.7
    )


def generate_questions(topic):
    llm = get_llm()

    chain = question_prompt | llm.with_structured_output(
        VivaQuestionSet
    )

    result = chain.invoke({"topic": topic})

    return result.questions


HTML = """
<!doctype html>
<html>
<head>
    <title>AI Viva Generator</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
        }
        select, input, button {
            padding: 10px;
            margin: 8px 0;
            width: 100%;
            box-sizing: border-box;
        }
        button {
            cursor: pointer;
            background: #222;
            color: white;
            border: none;
        }
        .error {
            color: #b00020;
            font-weight: bold;
        }
        .question {
            margin-top: 25px;
            padding: 18px;
            border: 1px solid #ddd;
            border-radius: 8px;
        }
    </style>
</head>
<body>

<h1>AI Viva Generator</h1>

{% if error %}
<p class="error">{{ error }}</p>
{% endif %}

<form method="post">

<label>Topic</label>
<select name="topic" required>
    {% for topic in topics %}
    <option value="{{ topic }}"
        {% if selected_topic == topic %}selected{% endif %}>
        {{ topic }}
    </option>
    {% endfor %}
</select>

<label>Starting Difficulty</label>
<select name="level" required>
    {% for level in levels %}
    <option value="{{ level }}"
        {% if selected_level == level %}selected{% endif %}>
        {{ level }}
    </option>
    {% endfor %}
</select>

<label>Number of Questions</label>
<input type="number" name="num_questions"
       min="1" max="15"
       value="{{ num_questions or 5 }}" required>

<button type="submit">Generate Viva</button>
</form>

{% if questions %}
<hr>
<h2>Viva Questions</h2>

{% for q in questions %}
<div class="question">
    <b>Q{{ loop.index }}. [{{ levels_by_num[q.difficulty] }}] {{ q.question }}</b>

    <p>A. {{ q.options[0] }}</p>
    <p>B. {{ q.options[1] }}</p>
    <p>C. {{ q.options[2] }}</p>
    <p>D. {{ q.options[3] }}</p>

    <p><b>Correct Answer:</b>
       {{ letters[q.correct_index] }}. {{ q.options[q.correct_index] }}
    </p>

    <p><b>Explanation:</b> {{ q.explanation }}</p>
    <p><b>Concept:</b> {{ q.concept }}</p>
</div>
{% endfor %}
{% endif %}

</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    questions = []
    error = None
    selected_topic = ""
    selected_level = ""
    num_questions = 5

    if request.method == "POST":
        selected_topic = request.form.get("topic", "")
        selected_level = request.form.get("level", "")
        raw_num = request.form.get("num_questions", "5")

        if selected_topic not in TOPICS:
            error = "Please select a valid topic."

        elif selected_level not in LEVELS:
            error = "Please select a valid difficulty."

        else:
            try:
                num_questions = int(raw_num)
            except ValueError:
                num_questions = 0

            if not 1 <= num_questions <= 15:
                error = "Number of questions must be between 1 and 15."

        if not error:
            try:
                all_questions = generate_questions(selected_topic)

                current_level = LEVEL_TO_NUM[selected_level]

                matching = [
                    q for q in all_questions
                    if q.difficulty == current_level
                ]

                others = [
                    q for q in all_questions
                    if q.difficulty != current_level
                ]

                questions = (matching + others)[:num_questions]

            except Exception as exc:
                error = f"Unable to generate questions: {exc}"

    return render_template_string(
        HTML,
        topics=TOPICS,
        levels=LEVELS,
        questions=questions,
        error=error,
        selected_topic=selected_topic,
        selected_level=selected_level,
        num_questions=num_questions,
        letters=OPTION_LETTERS,
        levels_by_num=NUM_TO_LEVEL
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
