from pathlib import Path
import random
import json
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from dotenv import load_dotenv
from defender_cards import DEFENDER_NATIVE_NAMES_ORDERED, get_dlnr_meta_by_native_name
from invader_cards import get_invader_cards_by_name
from game_logic import (
    load_species,
    load_invaders,
    load_defender_natives_ordered,
    generate_wave,
    init_battle,
    process_turn,
    score_for_wave,
)

app = Flask(__name__)
app.secret_key = "kiai-aina-dev-key"

TEAM_SIZE = 3
LEADERBOARD_FILE = Path(__file__).resolve().parent / "data" / "leaderboard.json"

# Load environment variables
load_dotenv()
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@kiaiaina.com")


def get_all_species():
    return load_species()


def load_leaderboard():
    """Load leaderboard from JSON file."""
    if not LEADERBOARD_FILE.exists():
        return []
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_leaderboard(leaderboard):
    """Save leaderboard to JSON file."""
    LEADERBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(leaderboard, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving leaderboard: {e}")


def add_to_leaderboard(player_name, email, score, waves_survived, difficulty):
    """Add a score to the leaderboard."""
    leaderboard = load_leaderboard()
    
    # Only add infinite mode scores to leaderboard
    if difficulty != "infinite":
        return False
    
    new_entry = {
        "player_name": player_name,
        "email": email,
        "score": score,
        "waves_survived": waves_survived,
        "difficulty": difficulty,
        "date": datetime.now().isoformat(),
    }
    
    leaderboard.append(new_entry)
    leaderboard.sort(key=lambda x: x["score"], reverse=True)
    
    # Notify previous top scorers if their score is beaten
    if len(leaderboard) > 1 and leaderboard[0]["score"] == score:
        notify_beaten_scores(new_entry, leaderboard)
    
    # Keep only top 100
    leaderboard = leaderboard[:100]
    save_leaderboard(leaderboard)
    
    return True


def get_top_leaderboard(limit=10):
    """Get top N scores from leaderboard."""
    leaderboard = load_leaderboard()
    return leaderboard[:limit]


def notify_beaten_scores(new_entry, leaderboard):
    """Send email notifications to players whose scores were beaten using SendGrid."""
    if not SENDGRID_API_KEY:
        print("Warning: SENDGRID_API_KEY not set. Email notifications disabled.")
        return
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        
        # Check if score beats others and send notifications
        for entry in leaderboard[1:]:
            if entry.get("email") and new_entry["score"] > entry["score"]:
                recipient_email = entry.get("email")
                recipient_name = entry.get("player_name", "Player")
                
                # Create HTML email content
                html_content = f"""
                <html>
                    <head>
                        <style>
                            body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                            .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                            .header {{ color: #a855f7; font-size: 24px; font-weight: bold; margin-bottom: 20px; text-align: center; }}
                            .content {{ color: #333; line-height: 1.6; margin-bottom: 20px; }}
                            .highlight {{ background-color: #f0e6ff; padding: 15px; border-left: 4px solid #a855f7; margin: 15px 0; }}
                            .score-box {{ background-color: #fef3c7; padding: 15px; border-radius: 6px; text-align: center; margin: 15px 0; }}
                            .score-old {{ color: #6b7280; font-size: 14px; }}
                            .score-new {{ color: #a855f7; font-size: 24px; font-weight: bold; }}
                            .footer {{ color: #9ca3af; font-size: 12px; text-align: center; margin-top: 20px; border-top: 1px solid #e5e7eb; padding-top: 15px; }}
                            .button {{ display: inline-block; background-color: #a855f7; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; margin: 15px 0; text-align: center; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="header">🏆 Your Leaderboard Score Was Beaten! 🏆</div>
                            <div class="content">
                                <p>Hi {recipient_name},</p>
                                <p>Unfortunately, your Infinite Mode score on the <strong>Kiai Aina</strong> leaderboard has been beaten!</p>
                                
                                <div class="highlight">
                                    <p><strong>{new_entry['player_name']}</strong> just scored <strong>{new_entry['score']} points</strong>!</p>
                                </div>
                                
                                <p>Here's the comparison:</p>
                                <div class="score-box">
                                    <div class="score-old">Your Previous Score: {entry['score']} points</div>
                                    <div style="margin: 10px 0;">→</div>
                                    <div class="score-new">New #1 Score: {new_entry['score']} points</div>
                                </div>
                                
                                <p>Don't worry! You can challenge them back and reclaim your spot on the leaderboard. Every game is a new opportunity to prove your skills!</p>
                                
                                <p style="text-align: center; margin: 20px 0;">
                                    <a href="http://localhost:5000/leaderboard" class="button">View Leaderboard</a>
                                </p>
                                
                                <p>Keep playing and keep improving! 🎮</p>
                                <p>Best regards,<br><strong>Kiai Aina Team</strong></p>
                            </div>
                            <div class="footer">
                                <p>This is an automated email from Kiai Aina Infinite Mode Leaderboard. Please do not reply to this email.</p>
                            </div>
                        </div>
                    </body>
                </html>
                """
                
                # Actual Email version
                text_content = f"""
                Your Leaderboard Score Was Beaten!
                
                Hi {recipient_name},
                
                Your Infinite Mode score on the Kiai Aina leaderboard has been beaten!
                
                {new_entry['player_name']} just scored {new_entry['score']} points!
                
                Your Previous Score: {entry['score']} points
                New #1 Score: {new_entry['score']} points
                
                Don't worry! You can challenge them back and reclaim your spot on the leaderboard.
                
                View Leaderboard: http://localhost:5000/leaderboard
                
                Keep playing and keep improving!
                
                Best regards,
                Kiai Aina Team
                """
                
                # Create and send email
                message = Mail(
                    from_email=SENDGRID_FROM_EMAIL,
                    to_emails=To(recipient_email),
                    subject=f"🏆 Your Kiai Aina Score Was Beaten! 🏆",
                    plain_text_content=text_content,
                    html_content=html_content
                )
                
                response = sg.send(message)
                print(f"✓ Email sent to {recipient_email} - Status: {response.status_code}")
                
    except Exception as e:
        print(f"✗ Error sending email notifications: {e}")
        print(f"  Make sure SENDGRID_API_KEY is set in your .env file")



def _build_run_chart(run_history: list[dict]) -> bool:
    """
    Build a static run chart image using pandas + matplotlib.
    Returns True when chart file was written, False if charting is unavailable.
    """
    if not run_history:
        return False
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
    except Exception:
        return False

    df = pd.DataFrame(run_history)
    if df.empty:
        return False

    for col in ("wave_num", "points", "damage_dealt", "damage_taken"):
        if col not in df.columns:
            df[col] = 0
    df = df.sort_values("wave_num")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), constrained_layout=True)

    colors = ["#2d6a4f" if bool(v) else "#c0392b" for v in df.get("player_won", [])]
    ax1.bar(df["wave_num"], df["points"], color=colors)
    ax1.set_title("Points by Wave")
    ax1.set_xlabel("Wave")
    ax1.set_ylabel("Points")
    ax1.grid(axis="y", alpha=0.25)

    ax2.plot(df["wave_num"], df["damage_dealt"], marker="o", color="#2563eb", label="Damage Dealt")
    ax2.plot(df["wave_num"], df["damage_taken"], marker="o", color="#dc2626", label="Damage Taken")
    ax2.set_title("Damage Trend by Wave")
    ax2.set_xlabel("Wave")
    ax2.set_ylabel("Damage")
    ax2.grid(alpha=0.25)
    ax2.legend()

    out_path = Path(__file__).resolve().parent / "static" / "run_summary_chart.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return True


@app.route("/")
def home():
    background_image = url_for("static", filename="background.png")
    title_image = url_for("static", filename="title.png")
    return render_template("home.html", bg_pic=background_image, title_pic=title_image)


@app.route("/difficulty")
def difficulty():
    """Display difficulty selection page."""
    background_image = url_for("static", filename="background.png")
    return render_template("difficulty.html", bg_pic=background_image)


@app.route("/leaderboard")
def leaderboard():
    """Display leaderboard."""
    background_image = url_for("static", filename="background.png")
    top_scores = get_top_leaderboard(10)
    leaderboard_data = [(idx, entry) for idx, entry in enumerate(top_scores)]
    return render_template("leaderboard.html", bg_pic=background_image, leaderboard=leaderboard_data)


@app.route("/start", methods=["POST"])
def start():
    session.clear()
    session["wave_num"] = 1
    session["score"] = 0
    session["waves_completed"] = 0
    session["run_history"] = []
    session["difficulty"] = request.form.get("difficulty", "normal")
    return redirect(url_for("game"))


@app.route("/choose-home", methods=["GET", "POST"])
def choose_home():
    """Legacy route: home selection was merged into the defender pick screen."""
    if "wave_num" not in session:
        return redirect(url_for("home"))
    return redirect(url_for("game"))


@app.route("/game")
def game():
    background_image = url_for("static", filename="background.png")

    if "wave_num" not in session:
        return redirect(url_for("home"))

    natives = load_defender_natives_ordered(DEFENDER_NATIVE_NAMES_ORDERED)
    dlnr_meta = get_dlnr_meta_by_native_name()

    natives_data = []
    for s in natives:
        m = dlnr_meta.get(s.name, {})
        natives_data.append(
            {
                "name": s.name,
                "display_name": m.get("display_name") or s.name.replace("_", " "),
                "common_line": m.get("common_line", ""),
                "image_url": m.get("image_url", ""),
                "profile_url": m.get("profile_url", ""),
                "scientific": m.get("scientific", ""),
                "health": s.health,
                "attack": s.attack,
                "facts": s.facts,
                "moves": [mv.to_dict() for mv in s.moves],
                "weak_to": s.weak_to,
                "strong_against": s.strong_against,
            }
        )


    return render_template(
        "game.html",
        wave_num=session["wave_num"],
        score=session["score"],
        natives=natives_data,
        team_size=TEAM_SIZE,
        bg_pic=background_image,

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
    background_image = url_for("static", filename="background.png")
    
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

    dlnr_meta = get_dlnr_meta_by_native_name()
    active_dlnr = dlnr_meta.get(active["name"], {})
    invader_cards = get_invader_cards_by_name()
    inv_card = invader_cards.get(inv["name"], {})

    return render_template(
        "battle.html",
        state=state,
        active=active,
        active_moves=active_moves,
        active_traits=active_traits,
        active_dlnr=active_dlnr,
        dlnr_meta=dlnr_meta,
        inv=inv,
        inv_card=inv_card,
        score=session["score"],
        bg_pic=background_image,
    )


@app.route("/battle/action", methods=["POST"])
def battle_action():

    background_image = url_for("static", filename="background.png")

    if "battle" not in session:
        return redirect(url_for("home"))

    move_name = request.form.get("move")
    state = session["battle"]

    if move_name and not state["battle_over"]:
        all_species = get_all_species()
        defender_name_map = {
            slug: meta.get("display_name") or slug
            for slug, meta in get_dlnr_meta_by_native_name().items()
        }
        invader_name_map = {
            slug: meta.get("display_name") or slug
            for slug, meta in get_invader_cards_by_name().items()
        }
        process_turn(
            state,
            move_name,
            all_species,
            defender_name_map=defender_name_map,
            invader_name_map=invader_name_map,
        )
        session["battle"] = state

    if state["battle_over"]:
        points = score_for_wave(state)
        session["score"] = session.get("score", 0) + points

        history = session.get("run_history", [])
        wave_analytics = state.get("analytics", {})
        defender_usage = wave_analytics.get("defender_usage", {})
        top_defender_slug = None
        if defender_usage:
            top_defender_slug = max(defender_usage.items(), key=lambda item: item[1])[0]
        defender_name_map = {
            slug: meta.get("display_name") or slug
            for slug, meta in get_dlnr_meta_by_native_name().items()
        }
        history.append({
            "wave_num": state["wave_num"],
            "player_won": state["player_won"],
            "points": points,
            "turns_taken": wave_analytics.get("turns_taken", 0),
            "damage_dealt": wave_analytics.get("total_damage_dealt", 0),
            "damage_taken": wave_analytics.get("total_damage_taken", 0),
            "energy_spent": wave_analytics.get("energy_spent", 0),
            "max_damage_dealt": wave_analytics.get("max_single_hit", 0),
            "max_damage_received": wave_analytics.get("max_damage_received", 0),
            "invaders_defeated": wave_analytics.get("invaders_defeated", 0),
            "defenders_fainted": wave_analytics.get("defenders_fainted", 0),
            "most_used_defender": (
                defender_name_map.get(top_defender_slug, top_defender_slug)
                if top_defender_slug
                else "N/A"
            ),
        })
        session["run_history"] = history

        if state["player_won"]:
            session["waves_completed"] = session.get("waves_completed", 0) + 1

        game_over = not state["player_won"]
        session["game_over"] = game_over

        # Keep session small: store only invader slugs, build facts in /result.
        session["last_fact_invader_names"] = [inv["name"] for inv in state["invaders"]]

        return redirect(url_for("result"))

    return redirect(url_for("battle", bg_pic=background_image))


@app.route("/result")
def result():

    background_image = url_for("static", filename="background.png")

    if "battle" not in session:
        return redirect(url_for("home"))

    state = session["battle"]
    analytics = state.get("analytics", {})
    turns = analytics.get("turns_taken", 0)
    dealt = analytics.get("total_damage_dealt", 0)
    taken = analytics.get("total_damage_taken", 0)
    max_received = analytics.get("max_damage_received", 0)
    energy_spent = analytics.get("energy_spent", 0)
    invaders_defeated = analytics.get("invaders_defeated", 0)
    defenders_fainted = analytics.get("defenders_fainted", 0)
    max_hit = analytics.get("max_single_hit", 0)
    move_usage = analytics.get("move_usage", {})
    defender_usage = analytics.get("defender_usage", {})
    top_move = None
    top_defender = None
    if move_usage:
        top_move = max(move_usage.items(), key=lambda item: item[1])
    if defender_usage:
        top_defender = max(defender_usage.items(), key=lambda item: item[1])
    defender_labels = get_dlnr_meta_by_native_name()

    total_team_max_hp = sum(m.get("max_hp", 0) for m in state.get("team", []))
    total_team_hp = sum(m.get("hp", 0) for m in state.get("team", []))
    team_survival_pct = (
        round((total_team_hp / total_team_max_hp) * 100, 1) if total_team_max_hp else 0.0
    )

    analytics_view = {
        "turns_taken": turns,
        "avg_damage_per_turn": round(dealt / turns, 1) if turns else 0.0,
        "avg_energy_per_turn": round(energy_spent / turns, 2) if turns else 0.0,
        "total_damage_dealt": dealt,
        "total_damage_taken": taken,
        "max_damage_received": max_received,
        "invaders_defeated": invaders_defeated,
        "defenders_fainted": defenders_fainted,
        "max_damage_dealt": max_hit,
        "top_move_name": top_move[0] if top_move else "N/A",
        "top_move_count": top_move[1] if top_move else 0,
        "top_defender_name": (
            (defender_labels.get(top_defender[0], {}).get("display_name") or top_defender[0])
            if top_defender
            else "N/A"
        ),
        "team_survival_pct": team_survival_pct,
    }

    facts_source = session.get("last_fact_invader_names", [])
    invader_cards = get_invader_cards_by_name()
    facts_view = []
    for inv_name in facts_source:
        inv_card = invader_cards.get(inv_name, {})
        desc_all = list(inv_card.get("description_points") or [])
        impact_all = list(inv_card.get("impact_points") or [])
        desc_pick = random.sample(desc_all, 3) if len(desc_all) > 3 else desc_all
        impact_pick = random.sample(impact_all, 3) if len(impact_all) > 3 else impact_all
        facts_view.append(
            {
                "species": inv_card.get("display_name") or inv_name,
                "title_line": inv_card.get("title_line") or inv_name,
                "profile_url": inv_card.get("profile_url"),
                "description_points": desc_pick,
                "impact_points": impact_pick,
            }
        )

    return render_template(
        "result.html",
        state=state,
        score=session["score"],
        game_over=session.get("game_over", False),
        facts=facts_view,
        analytics=analytics_view,
        bg_pic=background_image,
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
    run_history = session.get("run_history", [])
    total_waves = len(run_history)
    total_turns = sum(w.get("turns_taken", 0) for w in run_history)
    total_dealt = sum(w.get("damage_dealt", 0) for w in run_history)
    total_taken = sum(w.get("damage_taken", 0) for w in run_history)
    total_energy = sum(w.get("energy_spent", 0) for w in run_history)
    max_damage_dealt = max((w.get("max_damage_dealt", 0) for w in run_history), default=0)
    max_damage_received = max((w.get("max_damage_received", 0) for w in run_history), default=0)
    total_invaders_defeated = sum(w.get("invaders_defeated", 0) for w in run_history)
    total_defenders_fainted = sum(w.get("defenders_fainted", 0) for w in run_history)
    wins = sum(1 for w in run_history if w.get("player_won"))
    losses = total_waves - wins
    best_wave = max(run_history, key=lambda w: w.get("points", 0), default=None)
    defender_counts: dict[str, int] = {}
    for w in run_history:
        name = w.get("most_used_defender")
        if name and name != "N/A":
            defender_counts[name] = defender_counts.get(name, 0) + 1
    top_defender_name = (
        max(defender_counts.items(), key=lambda kv: kv[1])[0]
        if defender_counts
        else "N/A"
    )

    chart_ready = _build_run_chart(run_history)

    run_analytics = {
        "total_waves": total_waves,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round((wins / total_waves) * 100, 1) if total_waves else 0.0,
        "turns_taken": total_turns,
        "avg_damage_per_turn": round(total_dealt / total_turns, 1) if total_turns else 0.0,
        "avg_energy_per_turn": round(total_energy / total_turns, 2) if total_turns else 0.0,
        "team_survival_pct": round((wins / total_waves) * 100, 1) if total_waves else 0.0,
        "total_damage_dealt": total_dealt,
        "total_damage_taken": total_taken,
        "max_damage_received": max_damage_received,
        "max_damage_dealt": max_damage_dealt,
        "total_invaders_defeated": total_invaders_defeated,
        "total_defenders_fainted": total_defenders_fainted,
        "top_move_name": "N/A",
        "top_defender_name": top_defender_name,
        "best_wave_num": best_wave.get("wave_num") if best_wave else "N/A",
        "best_wave_points": best_wave.get("points", 0) if best_wave else 0,
    }

    background_image = url_for("static", filename="background.png")
    return render_template(
        "end.html",
        score=session.get("score", 0),
        run_history=run_history,
        wave_num=session.get("wave_num", 1),
        waves_completed=session.get("waves_completed", 0),
        run_analytics=run_analytics,
        chart_ready=chart_ready,
        chart_image_url=f"{url_for('static', filename='run_summary_chart.png')}?v={session.get('score', 0)}-{total_waves}",
        difficulty=session.get("difficulty", "normal"),
        bg_pic=background_image,
    )


@app.route("/compendium")
def compendium():
    """Display Species Compendium with all defenders and invaders."""
    # Load defenders with metadata
    natives = load_defender_natives_ordered(DEFENDER_NATIVE_NAMES_ORDERED)
    dlnr_meta = get_dlnr_meta_by_native_name()
    
    defenders_data = []
    for s in natives:
        m = dlnr_meta.get(s.name, {})
        defenders_data.append(
            {
                "name": s.name,
                "display_name": m.get("display_name") or s.name.replace("_", " "),
                "common_line": m.get("common_line", ""),
                "image_url": m.get("image_url", ""),
                "scientific": m.get("scientific", ""),
                "health": s.health,
                "attack": s.attack,
                "facts": s.facts,
            }
        )
    
    # Load invaders with metadata
    invader_cards = get_invader_cards_by_name()
    invaders_data = []
    for name, card in invader_cards.items():
        invaders_data.append(
            {
                "name": name,
                "display_name": card.get("display_name", name.replace("_", " ")),
                "common_line": card.get("common_line", ""),
                "scientific": card.get("scientific", ""),
                "health": card.get("health", 0),
                "attack": card.get("attack", 0),
                "facts": card.get("facts", []),
                "description_points": card.get("description_points", []),
                "image_url": card.get("image_url", ""),
            }
        )
    
    background_image = url_for("static", filename="background.png")
    
    return render_template(
        "compendium.html",
        defenders=defenders_data,
        invaders=invaders_data,
        bg_pic=background_image,
    )


@app.route("/save-score", methods=["POST"])
def save_score():
    """Save infinite mode score to leaderboard."""
    data = request.get_json()
    player_name = data.get("player_name", "Anonymous").strip()
    email = data.get("email", "").strip()
    
    if not player_name or not email:
        return jsonify({"success": False, "message": "Name and email required"}), 400
    
    # Validate email format (basic validation)
    if "@" not in email or "." not in email:
        return jsonify({"success": False, "message": "Invalid email format"}), 400
    
    score = session.get("score", 0)
    difficulty = session.get("difficulty", "normal")
    waves = len(session.get("run_history", []))
    
    # Only save if infinite mode
    if difficulty == "infinite":
        add_to_leaderboard(player_name, email, score, waves, difficulty)
        return jsonify({"success": True, "message": "Score saved!"}), 200
    else:
        return jsonify({"success": False, "message": "Only Infinite mode scores are tracked"}), 400


if __name__ == "__main__":
    app.run(debug=True)
