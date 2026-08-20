import os
from typing import List

from flask import Flask, request, render_template_string, session
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "viva-secret-key")

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


def save_questions(questions):
    session["viva_questions"] = [
        {
            "question": q.question,
            "options": q.options,
            "correct_index": q.correct_index,
            "explanation": q.explanation,
            "concept": q.concept,
            "difficulty": q.difficulty
        } for q in questions
    ]

def load_questions():
    return [VivaQuestion(**x) for x in session.get("viva_questions", [])]


HTML = """
<!doctype html>
<html><head><title>AI Viva Generator</title>
<style>
body{font-family:Arial;max-width:800px;margin:40px auto;padding:20px}
select,input,button{padding:10px;margin:8px 0;width:100%;box-sizing:border-box}
button{cursor:pointer;background:#222;color:white;border:0}
.error{color:#b00020;font-weight:bold}.question,.report{margin-top:20px;padding:18px;border:1px solid #ddd;border-radius:8px}
.option{width:auto}
</style></head><body>
<h1>AI Viva Generator</h1>
{% if error %}<p class="error">{{ error }}</p>{% endif %}

{% if not questions and not report %}
<form method="post">
<label>Topic</label>
<select name="topic" required>
{% for topic in topics %}<option value="{{topic}}" {% if selected_topic==topic %}selected{% endif %}>{{topic}}</option>{% endfor %}
</select>
<label>Starting Difficulty</label>
<select name="level" required>
{% for level in levels %}<option value="{{level}}" {% if selected_level==level %}selected{% endif %}>{{level}}</option>{% endfor %}
</select>
<label>Number of Questions</label>
<input type="number" name="num_questions" min="1" max="15" value="{{num_questions}}" required>
<button name="action" value="generate">Generate Viva</button>
</form>
{% endif %}

{% if questions %}
<h2>Viva Questions</h2>
<form method="post">
<input type="hidden" name="action" value="submit">
{% for q in questions %}
<div class="question">
<b>Q{{loop.index}}. [{{levels_by_num[q.difficulty]}}] {{q.question}}</b>
<p><label><input class="option" type="radio" name="answer_{{loop.index0}}" value="0" required> A. {{q.options[0]}}</label></p>
<p><label><input class="option" type="radio" name="answer_{{loop.index0}}" value="1"> B. {{q.options[1]}}</label></p>
<p><label><input class="option" type="radio" name="answer_{{loop.index0}}" value="2"> C. {{q.options[2]}}</label></p>
<p><label><input class="option" type="radio" name="answer_{{loop.index0}}" value="3"> D. {{q.options[3]}}</label></p>
</div>
{% endfor %}
<button type="submit">Submit Viva & Generate Report</button>
</form>
{% endif %}

{% if report %}
<div class="report">
<h2>📊 Viva Report</h2>
<p><b>Topic:</b> {{selected_topic}}</p>
<p><b>Total Questions:</b> {{total}}</p>
<p><b>Correct Answers:</b> {{correct}}</p>
<p><b>Wrong Answers:</b> {{wrong}}</p>
<p><b>Score:</b> {{score}}%</p>
<h3>Question Review</h3>
{% for item in review %}
<p><b>Q{{loop.index}}.</b> {{item.question}}<br>
Your answer: {{item.user_answer}}<br>
Correct answer: {{item.correct_answer}}<br>
Explanation: {{item.explanation}}</p>
{% endfor %}
</div>
<form method="get"><button>Start New Viva</button></form>
{% endif %}
</body></html>
"""



@app.route("/", methods=["GET", "POST"])
def home():
    questions=[]; error=None; report=False; review=[]
    selected_topic=""; selected_level=""; num_questions=5
    correct=wrong=score=0

    if request.method=="POST":
        action=request.form.get("action","")
        selected_topic=request.form.get("topic","")
        selected_level=request.form.get("level","")

        if action=="generate":
            try: num_questions=int(request.form.get("num_questions","5"))
            except ValueError: num_questions=0

            if selected_topic not in TOPICS:
                error="Please select a valid topic."
            elif selected_level not in LEVELS:
                error="Please select a valid difficulty."
            elif not 1 <= num_questions <= 15:
                error="Number of questions must be between 1 and 15."
            else:
                try:
                    all_questions=generate_questions(selected_topic)
                    level=LEVEL_TO_NUM[selected_level]
                    matching=[q for q in all_questions if q.difficulty==level]
                    others=[q for q in all_questions if q.difficulty!=level]
                    questions=(matching+others)[:num_questions]
                    save_questions(questions)
                except Exception as exc:
                    error=f"Unable to generate questions: {exc}"

        elif action=="submit":
            try:
                questions=load_questions()
                if not questions:
                    error="Viva session expired. Please generate a new viva."
                else:
                    for i,q in enumerate(questions):
                        val=request.form.get(f"answer_{i}")
                        if val is None:
                            error="Please answer every question."
                            break
                        user_index=int(val)
                        if user_index==q.correct_index: correct+=1
                        else: wrong+=1
                        review.append({
                            "question":q.question,
                            "user_answer":f"{OPTION_LETTERS[user_index]}. {q.options[user_index]}",
                            "correct_answer":f"{OPTION_LETTERS[q.correct_index]}. {q.options[q.correct_index]}",
                            "explanation":q.explanation
                        })
                    if not error:
                        total=len(questions)
                        score=round(correct/total*100,2) if total else 0
                        report=True
                        session.pop("viva_questions",None)
                        questions=[]
            except Exception as exc:
                error=f"Unable to generate report: {exc}"

    return render_template_string(HTML, topics=TOPICS, levels=LEVELS,
        questions=questions, error=error, selected_topic=selected_topic,
        selected_level=selected_level, num_questions=num_questions,
        letters=OPTION_LETTERS, levels_by_num=NUM_TO_LEVEL,
        report=report, review=review, total=len(review),
        correct=correct, wrong=wrong, score=score)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
