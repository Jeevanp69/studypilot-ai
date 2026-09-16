from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    uploads = db.relationship(
        "Upload",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )

    quiz_attempts = db.relationship(
        "QuizAttempt",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password,
        )


class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    filename = db.Column(
        db.String(255),
        nullable=False,
    )

    original_filename = db.Column(
        db.String(255),
        nullable=False,
    )

    stored_path = db.Column(
        db.String(500),
        nullable=False,
    )

    uploaded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    # Keep the relationship name expected by the existing main.py
    note = db.relationship(
        "GeneratedNote",
        backref="upload",
        uselist=False,
        cascade="all, delete-orphan",
    )


class GeneratedNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    summary = db.Column(
        db.Text,
        nullable=False,
    )

    # Keep the field names expected by the existing main.py
    flashcards_json = db.Column(
        db.Text,
        nullable=False,
    )

    quiz_json = db.Column(
        db.Text,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    upload_id = db.Column(
        db.Integer,
        db.ForeignKey("upload.id"),
        nullable=False,
        unique=True,
    )

    quiz_attempts = db.relationship(
        "QuizAttempt",
        backref="note",
        lazy=True,
        cascade="all, delete-orphan",
    )


class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    score = db.Column(
        db.Integer,
        nullable=False,
    )

    total = db.Column(
        db.Integer,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    note_id = db.Column(
        db.Integer,
        db.ForeignKey("generated_note.id"),
        nullable=False,
    )

    answers = db.relationship(
        "QuizAnswer",
        backref="attempt",
        lazy=True,
        cascade="all, delete-orphan",
    )


class QuizAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    question_index = db.Column(
        db.Integer,
        nullable=False,
    )

    selected_answer = db.Column(
        db.Text,
        nullable=False,
    )

    correct_answer = db.Column(
        db.Text,
        nullable=False,
    )

    is_correct = db.Column(
        db.Boolean,
        nullable=False,
    )

    attempt_id = db.Column(
        db.Integer,
        db.ForeignKey("quiz_attempt.id"),
        nullable=False,
    )