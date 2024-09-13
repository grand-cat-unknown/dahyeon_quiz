# app.py

from datetime import datetime

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy

from models import Answer, CorrectAnswer, GameState, Player, Question, db

app = Flask(__name__)
app.config["SECRET_KEY"] = "12345"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///quiz.db"
db.init_app(app)

socketio = SocketIO(app, async_mode="eventlet")

# Predefined questions
QUESTIONS = [
    "What is the capital of France?",
    "Who painted the Mona Lisa?",
    "What is the largest planet in our solar system?",
    "In which year did World War II end?",
    "What is the chemical symbol for gold?",
]


def get_or_create_game_state():
    game_state = GameState.query.first()
    if not game_state:
        game_state = GameState(current_question_index=0)
        db.session.add(game_state)
        db.session.commit()
    return game_state


def update_game_state(index):
    game_state = get_or_create_game_state()
    game_state.current_question_index = index
    db.session.commit()


@app.route("/")
def index():
    return "Welcome to the Birthday Quiz Game!"


@app.route("/player")
def player_portal():
    return render_template("player.html")


@app.route("/birthday_girl")
def birthday_girl_portal():
    return render_template("birthday_girl.html")


@app.route("/tv")
def tv_display():
    return render_template("tv_display.html")


@app.route("/admin")
def admin_portal():
    return render_template("admin.html")


@socketio.on("connect")
def handle_connect():
    print("Client connected")
    game_state = get_or_create_game_state()
    emit(
        "new_question", {"question_text": QUESTIONS[game_state.current_question_index]}
    )


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


@socketio.on("join")
def on_join(data):
    room = data["room"]
    join_room(room)
    print(f"Client joined room {room}")



@socketio.on("submit_answer")
def handle_submit_answer(data):
    player_name = data["player_name"]
    answer_text = data["answer_text"]

    player = Player.query.filter_by(name=player_name).first()
    if not player:
        player = Player(name=player_name)
        db.session.add(player)
        db.session.commit()

    game_state = get_or_create_game_state()
    question = Question.query.filter_by(
        text=QUESTIONS[game_state.current_question_index]
    ).first()
    if not question:
        question = Question(
            text=QUESTIONS[game_state.current_question_index],
            timestamp=datetime.utcnow(),
        )
        db.session.add(question)
        db.session.commit()

    answer = Answer(
        player_id=player.id,
        question_id=question.id,
        text=answer_text,
        timestamp=datetime.utcnow(),
    )
    db.session.add(answer)
    db.session.commit()

    emit(
        "new_answer",
        {
            "answer_id": answer.id,
            "player_name": player.name,
            "answer_text": answer.text,
        },
        broadcast=True,  # Changed from room="birthday_girl" to broadcast=True
    )


@socketio.on("select_correct_answer")
def handle_select_correct_answer(data):
    answer_id = data["answer_id"]

    answer = Answer.query.get(answer_id)
    question = answer.question

    correct_answer = CorrectAnswer(
        question_id=question.id, answer_id=answer_id, player_id=answer.player_id
    )
    db.session.add(correct_answer)

    # Update player's score
    answer.player.score += 1
    db.session.commit()

    emit(
        "correct_answer_selected",
        {
            "question_id": question.id,
            "answer_text": answer.text,
            "player_name": answer.player.name,
        },
        broadcast=True,
    )

    # Send updated scores to admin
    players = Player.query.order_by(Player.score.desc()).all()
    scores = [{"name": player.name, "score": player.score} for player in players]
    emit("update_scores", scores, room="admin")

    # Move to the next question
    game_state = get_or_create_game_state()
    game_state.current_question_index += 1
    if game_state.current_question_index < len(QUESTIONS):
        db.session.commit()
        emit(
            "new_question",
            {"question_text": QUESTIONS[game_state.current_question_index]},
            broadcast=True,
        )
    else:
        emit("game_over", broadcast=True)


@socketio.on("start_game")
def handle_start_game():
    update_game_state(0)
    emit("new_question", {"question_text": QUESTIONS[0]}, broadcast=True)


@socketio.on("reset_game")
def handle_reset_game():
    update_game_state(0)
    Player.query.update({Player.score: 0})
    db.session.commit()
    emit("new_question", {"question_text": QUESTIONS[0]}, broadcast=True)

    # Send updated scores to admin after reset
    players = Player.query.order_by(Player.score.desc()).all()
    scores = [{"name": player.name, "score": player.score} for player in players]
    emit("update_scores", scores, room="admin")


@socketio.on("next_question")
def handle_next_question():
    game_state = get_or_create_game_state()
    if game_state.current_question_index < len(QUESTIONS) - 1:
        game_state.current_question_index += 1
        db.session.commit()
        emit(
            "new_question",
            {"question_text": QUESTIONS[game_state.current_question_index]},
            broadcast=True,
        )


@socketio.on("previous_question")
def handle_previous_question():
    game_state = get_or_create_game_state()
    if game_state.current_question_index > 0:
        game_state.current_question_index -= 1
        db.session.commit()
        emit(
            "new_question",
            {"question_text": QUESTIONS[game_state.current_question_index]},
            broadcast=True,
        )


@app.route("/get_scores", methods=["GET"])
def get_scores():
    players = Player.query.order_by(Player.score.desc()).all()
    scores = [{"name": player.name, "score": player.score} for player in players]
    return jsonify(scores)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=5001, debug=True)
