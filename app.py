from flask import Flask, render_template, request, redirect, url_for, session
from game_logic import load_species, load_invaders, generate_wave, init_battle, process_turn, score_for_wave

app = Flask(__name__)
app.secret_key = "kiai-aina-dev-key"

MAX_WAVES = 10
TEAM_SIZE = 3


def get_all_species():
    return load_species()


@app.route("/")
def home():
    background_image = url_for("static", filename="background.png")
    title_image = url_for("static", filename="title.png")
    return render_template("home.html", bg_pic=background_image, title_pic=title_image)

@app.route("/start", methods=["POST"])
def start():
    session.clear()
    session["wave_num"] = 1
    session["score"] = 0
    session["run_history"] = []
    return redirect(url_for("choose_home"))


HOME_SPECIES = [
    {
        "name": "Nēnē",
        "scientific": "Branta sandvicensis",
        "key": "nene",
        "image": "nene_bird_pic.jpg",
        "placeholder": "information placeholder",
    },
    {
        "name": "ʻAlalā",
        "scientific": "Corvus hawaiiensis",
        "key": "alala",
        "image": "alala_bird_pic.jpg",
        "placeholder": "information placeholder",
    },
    {
        "name": "ʻŌpeʻapeʻa",
        "scientific": "Lasiurus semotus",
        "key": "opeapea",
        "image": "opeapea_bat_pic.jpg",
        "placeholder": "information placeholder",
    },
]


@app.route("/choose-home", methods=["GET"])
def choose_home():
    if "wave_num" not in session:
        return redirect(url_for("home"))
    return render_template("choose_home.html", species=HOME_SPECIES)


@app.route("/choose-home", methods=["POST"])
def choose_home_post():
    if "wave_num" not in session:
        return redirect(url_for("home"))
    chosen = request.form.get("home_species")
    if not chosen:
        return redirect(url_for("choose_home"))
    session["home_species"] = chosen
    return redirect(url_for("game"))


@app.route("/game")
def game():
    if "wave_num" not in session:
        return redirect(url_for("home"))

    all_species = get_all_species()
    natives = [s for s in all_species if not s.is_invasive]

    # Pass moves as plain dicts so Jinja can iterate them
    natives_data = [
        {
            "name": s.name,
            "health": s.health,
            "attack": s.attack,
            "facts": s.facts,
            "moves": [m.to_dict() for m in s.moves],
            "weak_to": s.weak_to,
            "strong_against": s.strong_against,
        }
        for s in natives
    ]

    return render_template(
        "game.html",
        wave_num=session["wave_num"],
        score=session["score"],
        natives=natives_data,
        team_size=TEAM_SIZE,
    )


@app.route("/battle/start", methods=["POST"])
def battle_start():
    if "wave_num" not in session:
        return redirect(url_for("home"))

    selected = request.form.getlist("natives")[:TEAM_SIZE]
    if len(selected) < 1:
        return redirect(url_for("game"))

    all_species = get_all_species()
    wave = generate_wave(session["wave_num"], all_species)

    battle_state = init_battle(selected, wave, all_species)
    session["battle"] = battle_state
    return redirect(url_for("battle"))


@app.route("/battle")
def battle():
    if "battle" not in session:
        return redirect(url_for("home"))

    state = session["battle"]
    all_species = get_all_species()
    species_map = {s.name: s for s in all_species}

    # Active defender and their moves/traits
    active = state["team"][state["active_idx"]]
    active_species = species_map.get(active["name"])
    active_moves = [m.to_dict() for m in active_species.moves] if active_species else []
    active_traits = {
        "weak_to": active_species.weak_to if active_species else [],
        "strong_against": active_species.strong_against if active_species else [],
    }

    # Current invader
    inv = state["invaders"][state["invader_idx"]]

    return render_template(
        "battle.html",
        state=state,
        active=active,
        active_moves=active_moves,
        active_traits=active_traits,
        inv=inv,
        score=session["score"],
    )


@app.route("/battle/action", methods=["POST"])
def battle_action():
    if "battle" not in session:
        return redirect(url_for("home"))

    move_name = request.form.get("move")
    state = session["battle"]

    if move_name and not state["battle_over"]:
        all_species = get_all_species()
        process_turn(state, move_name, all_species)
        session["battle"] = state

    if state["battle_over"]:
        points = score_for_wave(state)
        session["score"] = session.get("score", 0) + points

        history = session.get("run_history", [])
        history.append({
            "wave_num": state["wave_num"],
            "player_won": state["player_won"],
            "points": points,
        })
        session["run_history"] = history

        game_over = not state["player_won"] or session["wave_num"] >= MAX_WAVES
        session["game_over"] = game_over

        # Collect invader facts for result screen
        all_species = get_all_species()
        species_map = {s.name: s for s in all_species}
        invaders = load_invaders()
        inv_map = {s.name: s for s in invaders}
        facts = []
        for inv in state["invaders"]:
            s = inv_map.get(inv["name"]) or species_map.get(inv["name"])
            if s and s.facts:
                facts.append({"species": inv["name"], "fact": s.facts[0]})
        session["last_facts"] = facts

        return redirect(url_for("result"))

    return redirect(url_for("battle"))


@app.route("/result")
def result():
    if "battle" not in session:
        return redirect(url_for("home"))

    state = session["battle"]
    return render_template(
        "result.html",
        state=state,
        score=session["score"],
        game_over=session.get("game_over", False),
        facts=session.get("last_facts", []),
    )


@app.route("/next", methods=["POST"])
def next_wave():
    if session.get("game_over"):
        return redirect(url_for("end"))
    session["wave_num"] = session.get("wave_num", 1) + 1
    session.pop("battle", None)
    return redirect(url_for("game"))


@app.route("/end")
def end():
    return render_template(
        "end.html",
        score=session.get("score", 0),
        run_history=session.get("run_history", []),
        wave_num=session.get("wave_num", 1),
    )


if __name__ == "__main__":
    app.run(debug=True)
