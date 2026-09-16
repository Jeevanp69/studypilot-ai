"""
Main blueprint — dashboard, upload + processing, and viewing a
generated note. Built after auth was already working on its own.
"""

import os
import json
import uuid

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from app import limiter
from . import db
from .models import GeneratedNote, QuizAttempt, QuizAnswer, Upload
from app.ai_helper import extract_text_from_pdf, generate_notes_from_text

main_bp = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@main_bp.route("/")
def index():
    return redirect(url_for("main.dashboard")) if current_user.is_authenticated else redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    uploads = (
        Upload.query
        .filter_by(user_id=current_user.id)
        .order_by(Upload.uploaded_at.desc())
        .all()
    )

    attempts = (
        QuizAttempt.query
        .filter_by(user_id=current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )

    total_quizzes = len(attempts)

    total_questions = sum(
        attempt.total for attempt in attempts
    )

    total_correct = sum(
        attempt.score for attempt in attempts
    )

    average_score = (
        round(
            (total_correct / total_questions) * 100,
            1,
        )
        if total_questions
        else 0
    )

    # -------------------------------
    # Performance insight
    # -------------------------------

    if total_quizzes == 0:
        performance_message = (
            "Complete your first quiz to unlock "
            "personalized learning insights."
        )
    elif average_score >= 80:
        performance_message = (
            "Strong performance. Keep revising "
            "to maintain your understanding."
        )
    elif average_score >= 60:
        performance_message = (
            "Good foundation. Focus on missed questions "
            "to strengthen weak areas."
        )
    else:
        performance_message = (
            "More revision is recommended. "
            "Review your notes and retry the quizzes."
        )

    # -------------------------------
    # Recent attempts
    # -------------------------------

    recent_attempts = attempts[:5]

    # -------------------------------
    # Weak questions
    # -------------------------------

    weak_answers = (
        QuizAnswer.query
        .join(QuizAttempt)
        .filter(
            QuizAttempt.user_id == current_user.id,
            QuizAnswer.is_correct.is_(False),
        )
        .order_by(QuizAttempt.created_at.desc())
        .limit(10)
        .all()
    )

    weak_questions = []

    for answer in weak_answers:
        try:
            quiz_questions = json.loads(answer.attempt.note.quiz_json)

            question = quiz_questions[
                answer.question_index
            ]

            weak_questions.append(
                {
                    "question": question.get(
                        "question",
                        "Unknown question",
                    ),
                    "correct_answer": answer.correct_answer,
                    "selected_answer": answer.selected_answer,
                    "note_id": answer.attempt.note.id,
                }
            )

        except (
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
        ):
            continue

    return render_template(
        "dashboard.html",
        uploads=uploads,
        attempts=attempts,
        recent_attempts=recent_attempts,
        total_quizzes=total_quizzes,
        average_score=average_score,
        performance_message=performance_message,
        weak_questions=weak_questions,
    )


@main_bp.route("/upload", methods=["GET", "POST"])
@login_required
@limiter.limit("5 per day")  # small addition, but it's what a "real" app has
def upload():
    if request.method == "POST":
        file = request.files.get("file")

        if file is None or file.filename == "":
            flash("Please choose a PDF file.")
            return redirect(url_for("main.upload"))

        if not allowed_file(file.filename):
            flash("Only PDF files are supported right now.")
            return redirect(url_for("main.upload"))

        # Unique filename on disk avoids collisions between users
        # uploading files with the same name.
        safe_name = secure_filename(file.filename)
        stored_name = f"{uuid.uuid4().hex}_{safe_name}"
        stored_path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)
        file.save(stored_path)

        upload_record = Upload(
            filename=stored_name,
            original_filename=file.filename,
            stored_path=stored_path,
            user_id=current_user.id,
        )
        db.session.add(upload_record)
        db.session.commit()

        try:
            text = extract_text_from_pdf(stored_path)
            result = generate_notes_from_text(text)

            note = GeneratedNote(
                upload_id=upload_record.id,
                summary=result["summary"],
                flashcards_json=json.dumps(result["flashcards"]),
                quiz_json=json.dumps(result["quiz"]),
            )
            db.session.add(note)
            db.session.commit()

            try:
                if os.path.exists(stored_path):
                    os.remove(stored_path)
            except OSError:
                current_app.logger.warning(
                    "Could not remove temporary upload: %s",
                    stored_path,
                )

        except Exception:
            current_app.logger.exception(
                "Study material generation failed"
            )

            flash(
                "Something went wrong while generating your study material. "
                "Please try again.",
                "danger",
            )

            return redirect(url_for("main.dashboard"))

        return redirect(url_for("main.view_note", upload_id=upload_record.id))

    return render_template("upload.html")


@main_bp.route("/note/<int:upload_id>")
@login_required
def view_note(upload_id):
    upload_record = Upload.query.get_or_404(upload_id)

    if upload_record.user_id != current_user.id:
        flash("You don't have access to that.")
        return redirect(url_for("main.dashboard"))

    note = upload_record.note
    flashcards = json.loads(note.flashcards_json)
    quiz = json.loads(note.quiz_json)

    return render_template(
        "view_note.html",
        upload=upload_record,
        note=note,
        summary=note.summary,
        flashcards=flashcards,
        quiz=quiz,
    )


@main_bp.route("/quiz/<int:note_id>", methods=["GET", "POST"])
@login_required
def quiz(note_id):
    note = GeneratedNote.query.get_or_404(note_id)

    # Make sure the logged-in user owns this study material.
    if note.upload.user_id != current_user.id:
        flash("You don't have access to that.")
        return redirect(url_for("main.dashboard"))

    try:
        quiz_questions = json.loads(note.quiz_json)
    except (TypeError, json.JSONDecodeError):
        flash("Quiz data is invalid.")
        return redirect(url_for("main.dashboard"))

    if not isinstance(quiz_questions, list) or not quiz_questions:
        flash("No quiz questions are available.")
        return redirect(url_for("main.view_note", upload_id=note.upload_id))

    if request.method == "POST":
        score = 0
        answers = []

        for index, question in enumerate(quiz_questions):
            selected = request.form.get(
                f"question_{index}",
                "",
            ).strip()

            correct = str(
                question.get("answer", "")
            ).strip()

            is_correct = selected == correct

            if is_correct:
                score += 1

            answers.append(
                {
                    "question_index": index,
                    "selected_answer": selected or "Not answered",
                    "correct_answer": correct,
                    "is_correct": is_correct,
                }
            )

        attempt = QuizAttempt(
            score=score,
            total=len(quiz_questions),
            user_id=current_user.id,
            note_id=note.id,
        )

        db.session.add(attempt)
        db.session.flush()

        for answer in answers:
            quiz_answer = QuizAnswer(
                question_index=answer["question_index"],
                selected_answer=answer["selected_answer"],
                correct_answer=answer["correct_answer"],
                is_correct=answer["is_correct"],
                attempt_id=attempt.id,
            )

            db.session.add(quiz_answer)

        db.session.commit()

        return redirect(
            url_for(
                "main.quiz_result",
                attempt_id=attempt.id,
            )
        )

    return render_template(
        "quiz.html",
        note=note,
        quiz=quiz_questions,
    )


@main_bp.route("/quiz/result/<int:attempt_id>")
@login_required
def quiz_result(attempt_id):
    attempt = QuizAttempt.query.get_or_404(attempt_id)

    # Prevent users from viewing another user's results.
    if attempt.user_id != current_user.id:
        flash("You don't have access to that result.")
        return redirect(url_for("main.dashboard"))

    try:
        quiz_questions = json.loads(attempt.note.quiz_json)
    except (TypeError, json.JSONDecodeError):
        quiz_questions = []

    questions_by_index = {
        index: question
        for index, question in enumerate(quiz_questions)
    }

    results = []

    for answer in attempt.answers:
        question = questions_by_index.get(
            answer.question_index,
            {},
        )

        results.append(
            {
                "question": question.get(
                    "question",
                    f"Question {answer.question_index + 1}",
                ),
                "selected_answer": answer.selected_answer,
                "correct_answer": answer.correct_answer,
                "is_correct": answer.is_correct,
                "explanation": question.get(
                    "explanation",
                    "",
                ),
            }
        )

    percentage = (
        round((attempt.score / attempt.total) * 100, 1)
        if attempt.total
        else 0
    )

    return render_template(
        "quiz_result.html",
        attempt=attempt,
        results=results,
        percentage=percentage,
    )
    
    @main_bp.route("/health")
    def health():
        return {
        "status": "ok",
        "service": "StudyPilot AI",
    }, 200
