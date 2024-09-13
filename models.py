# models.py

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Player(db.Model):
    __tablename__ = "player"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(50), unique=True, nullable=False)
    score = db.Column(db.Integer, default=0)

    answers = db.relationship("Answer", backref="player", lazy=True)


class Question(db.Model):
    __tablename__ = "question"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    answers = db.relationship("Answer", backref="question", lazy=True)
    correct_answer = db.relationship(
        "CorrectAnswer", backref="question", lazy=True, uselist=False
    )


class Answer(db.Model):
    __tablename__ = "answer"
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CorrectAnswer(db.Model):
    __tablename__ = "correct_answer"
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    answer_id = db.Column(db.Integer, db.ForeignKey("answer.id"), nullable=False)

class GameState(db.Model):
    __tablename__ = "game_state"
    id = db.Column(db.Integer, primary_key=True)
    current_question_index = db.Column(db.Integer, default=0)