from flask import Flask, render_template, request, redirect, url_for, session
from game_logic import load_species, generate_wave, resolve_wave, update_score, get_max_defenders

app = Flask(__name__)
app.secret_key = "kiai-aina-dev-key"

MAX_WAVES = 10
MAX_CONSECUTIVE_LOSSES = 3


def get_all_species():
    return load_species()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/start", methods=["POST"])
def start():
    session.clear()
    session["wave_num"] = 1
    session["score"] = 0
    session["run_history"] = []
    session["consecutive_losses"] = 0
    return redirect(url_for("game"))


@app.route("/game")
def game():
    if "wave_num" not in session:
        return redirect(url_for("home"))

    all_species = get_all_species()
    natives = [s for s in all_species if not s.is_invasive]
    wave = generate_wave(session["wave_num"], all_species)

    # store current wave invaders in session so /resolve can reconstruct them
    session["current_wave_invaders"] = [s.name for s in wave.invaders]
    session["current_wave_difficulty"] = wave.difficulty

    max_defenders = get_max_defenders(session["wave_num"])
    session["max_defenders"] = max_defenders

    return render_template("game.html",
        wave_num=session["wave_num"],
        difficulty=wave.difficulty,
        invaders=wave.invaders,
        natives=natives,
        score=session["score"],
        max_defenders=max_defenders
    )


@app.route("/resolve", methods=["POST"])
def resolve():
    if "wave_num" not in session:
        return redirect(url_for("home"))

    selected_names = request.form.getlist("natives")
    max_defenders = session.get("max_defenders", 1)

    if not selected_names:
        return redirect(url_for("game"))

    selected_names = selected_names[:max_defenders]

    all_species = get_all_species()
    species_map = {s.name: s for s in all_species}

    selected_natives = [species_map[name] for name in selected_names if name in species_map]
    invaders = [species_map[name] for name in session["current_wave_invaders"] if name in species_map]

    from species import Wave
    wave = Wave(
        wave_num=session["wave_num"],
        invaders=invaders,
        difficulty=session["current_wave_difficulty"]
    )

    result = resolve_wave(selected_natives, wave)
    session["score"] = update_score(result, session["score"])

    if not result["wave_won"]:
        session["consecutive_losses"] = session.get("consecutive_losses", 0) + 1
    else:
        session["consecutive_losses"] = 0

    history = session.get("run_history", [])
    history.append(result)
    session["run_history"] = history

    game_over = (
        session["consecutive_losses"] >= MAX_CONSECUTIVE_LOSSES or
        session["wave_num"] >= MAX_WAVES
    )

    session["last_result"] = result
    session["game_over"] = game_over

    return redirect(url_for("result"))


@app.route("/result")
def result():
    if "last_result" not in session:
        return redirect(url_for("home"))

    facts = []
    if "current_wave_invaders" in session:
        all_species = get_all_species()
        species_map = {s.name: s for s in all_species}
        for name in session["current_wave_invaders"]:
            s = species_map.get(name)
            if s and s.facts:
                facts.append({"species": s.name, "fact": s.facts[0]})

    return render_template("result.html",
        result=session["last_result"],
        score=session["score"],
        game_over=session["game_over"],
        facts=facts
    )


@app.route("/next", methods=["POST"])
def next_wave():
    if session.get("game_over"):
        return redirect(url_for("end"))
    session["wave_num"] = session.get("wave_num", 1) + 1
    return redirect(url_for("game"))


@app.route("/end")
def end():
    return render_template("end.html",
        score=session.get("score", 0),
        run_history=session.get("run_history", []),
        wave_num=session.get("wave_num", 1)
    )


if __name__ == "__main__":
    app.run(debug=True)
