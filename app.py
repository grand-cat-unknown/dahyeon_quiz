# app.py

import random
import string
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy

from models import Answer, CorrectAnswer, GameState, Player, Question, db

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key_here"  # Change this to a random secret key
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///quiz.db"
db.init_app(app)

socketio = SocketIO(app, async_mode="eventlet")

# Predefined questions
QUESTIONS = [
    {
        "text": "What is the capital of France?",
        "options": ["London", "Berlin", "Paris", "Madrid"]
    },
    {
        "text": "Who painted the Mona Lisa?",
        "options": ["Vincent van Gogh", "Leonardo da Vinci", "Pablo Picasso", "Claude Monet"]
    },
    {
        "text": "What is the largest planet in our solar system?",
        "options": ["Earth", "Jupiter", "Saturn", "Mars"]
    },
    {
        "text": "In which year did World War II end?",
        "options": ["1943", "1945", "1947", "1950"]
    },
    {
        "text": "What is the chemical symbol for gold?",
        "options": ["Au", "Ag", "Fe", "Cu"]
    },
]

def generate_player_id():
    return "".join(random.choices(string.ascii_uppercase, k=4))

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
    player_id = request.args.get("player_id")
    if player_id:
        player = Player.query.filter_by(player_id=player_id).first()
        if player:
            return render_template(
                "player.html", player_name=player.name, player_id=player_id
            )
    return render_template("player.html", player_name=None, player_id=None)


@socketio.on("register_player")
def register_player(data):
    name = data["name"]
    player_id = generate_player_id()

    while Player.query.filter_by(player_id=player_id).first():
        player_id = generate_player_id()

    new_player = Player(player_id=player_id, name=name)
    db.session.add(new_player)
    db.session.commit()

    emit("player_registered", {"name": name, "player_id": player_id})

    # Send updated player list to admin
    players = Player.query.all()
    player_data = [
        {"name": player.name, "player_id": player.player_id} for player in players
    ]
    emit("update_players", player_data, room="admin")


@app.route("/birthday_girl")
def birthday_girl_portal():
    game_state = get_or_create_game_state()
    current_question_index = game_state.current_question_index
    current_question = QUESTIONS[current_question_index]

    return render_template(
        "birthday_girl.html",
        current_question=current_question["text"],
        options=current_question["options"],
    )


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
    current_question = QUESTIONS[game_state.current_question_index]
    emit(
        "new_question",
        {
            "question_text": current_question["text"],
            "options": current_question["options"]
        }
    )


@socketio.on("get_game_state")
def handle_get_game_state():
    game_state = get_or_create_game_state()
    current_question = QUESTIONS[game_state.current_question_index]

    emit("game_state", {
        "question_text": current_question["text"],
        "options": current_question["options"]
    })


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
        print(f"Player not found: {player_name}")
        return

    game_state = get_or_create_game_state()
    current_question = QUESTIONS[game_state.current_question_index]
    question = Question.query.filter_by(text=current_question["text"]).first()
    if not question:
        question = Question(text=current_question["text"], timestamp=datetime.utcnow())
        db.session.add(question)
        db.session.commit()

    # Check if player has already answered this question
    existing_answer = Answer.query.filter_by(
        player_id=player.id, question_id=question.id
    ).first()
    if existing_answer:
        print(f"Player {player_name} has already answered this question")
        emit(
            "answer_error",
            {"message": "You have already answered this question"},
            room=request.sid,
        )
        return

    answer = Answer(
        player_id=player.id,
        question_id=question.id,
        text=answer_text,
        timestamp=datetime.utcnow(),
    )
    db.session.add(answer)
    db.session.commit()

    print(f"New answer submitted: {player_name} - {answer_text}")

    emit(
        "new_answer",
        {
            "answer_id": answer.id,
            "player_name": player.name,
            "answer_text": answer.text,
        },
        broadcast=True,
    )

    # Confirm to the player that their answer was recorded
    emit(
        "answer_recorded",
        {"message": "Your answer has been recorded"},
        room=request.sid,
    )


@socketio.on("select_correct_option")
def handle_select_correct_option(data):
    option_id = data["option_id"]
    game_state = get_or_create_game_state()
    game_state.correct_option = option_id
    db.session.commit()

    emit("correct_option_selected", {"option_id": option_id}, broadcast=True)


@socketio.on("player_select_option")
def handle_player_select_option(data):
    player_name = data["player_name"]
    option_id = data["option_id"]
    
    player = Player.query.filter_by(name=player_name).first()
    game_state = get_or_create_game_state()

    if option_id == game_state.correct_option:
        player.score += 1
        db.session.commit()
        emit("option_result", {"correct": True}, room=request.sid)
    else:
        emit("option_result", {"correct": False}, room=request.sid)

    # Send updated scores to admin
    players = Player.query.order_by(Player.score.desc()).all()
    scores = [{"name": player.name, "score": player.score} for player in players]
    emit("update_scores", scores, room="admin")


@socketio.on("start_game")
def handle_start_game():
    update_game_state(0)
    current_question = QUESTIONS[0]
    emit(
        "new_question",
        {
            "question_text": current_question["text"],
            "options": current_question["options"]
        },
        broadcast=True
    )


@socketio.on("reset_game")
def handle_reset_game():
    with app.app_context():
        # Drop all tables
        db.drop_all()

        # Recreate all tables
        db.create_all()

        # Reinitialize game state
        game_state = GameState(current_question_index=0, correct_option=None)
        db.session.add(game_state)
        db.session.commit()

    current_question = QUESTIONS[0]
    emit(
        "new_question",
        {
            "question_text": current_question["text"],
            "options": current_question["options"]
        },
        broadcast=True
    )
    emit("game_reset", broadcast=True)

    # Send empty scores to admin after reset
    emit("update_scores", [], room="admin")

    print("Game reset: Database cleared and reinitialized")


@socketio.on("next_question")
def handle_next_question():
    game_state = get_or_create_game_state()
    if game_state.current_question_index < len(QUESTIONS) - 1:
        game_state.current_question_index += 1
        game_state.correct_option = None
        db.session.commit()
        current_question = QUESTIONS[game_state.current_question_index]
        emit(
            "new_question",
            {
                "question_text": current_question["text"],
                "options": current_question["options"]
            },
            broadcast=True,
        )
    else:
        emit("game_over", broadcast=True)


@socketio.on("previous_question")
def handle_previous_question():
    game_state = get_or_create_game_state()
    if game_state.current_question_index > 0:
        game_state.current_question_index -= 1
        db.session.commit()
        current_question = QUESTIONS[game_state.current_question_index]
        emit(
            "new_question",
            {
                "question_text": current_question["text"],
                "options": current_question["options"]
            },
            broadcast=True,
        )


@app.route("/get_scores", methods=["GET"])
def get_scores():
    players = Player.query.order_by(Player.score.desc()).all()
    scores = [{"name": player.name, "score": player.score} for player in players]
    return jsonify(scores)


@app.route("/get_players", methods=["GET"])
def get_players():
    players = Player.query.all()
    player_data = [
        {"name": player.name, "player_id": player.player_id, "score": player.score}
        for player in players
    ]
    return jsonify(player_data)


@app.route("/update_score", methods=["POST"])
def update_score():
    data = request.json
    player_id = data.get("player_id")
    new_score = data.get("score")

    player = Player.query.filter_by(player_id=player_id).first()
    if player:
        player.score = int(new_score)
        db.session.commit()

        # Emit updated scores to all clients
        players = Player.query.order_by(Player.score.desc()).all()
        scores = [{"name": p.name, "score": p.score} for p in players]
        socketio.emit("update_scores", scores, namespace='/')  # Use namespace='/' for the default namespace

        return jsonify({"success": True})
    else:
        return jsonify({"success": False}), 404

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=5001, debug=True)