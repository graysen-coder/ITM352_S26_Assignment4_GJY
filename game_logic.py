import json
import random
from species import Species, Wave, Move

DIFFICULTY_SETTINGS = {
    "easy":     {"health_mult": 0.7,  "attack_mult": 0.8},
    "normal":   {"health_mult": 1.0,  "attack_mult": 1.0},
    "hard":     {"health_mult": 1.3,  "attack_mult": 1.25},
    "infinite": {"health_mult": 1.5,  "attack_mult": 1.4},
}


# This function takes a single JSON entry dict and constructs a Species object from it,
# converting the raw moves list into Move objects before passing everything to the Species constructor
def _species_from_entry(entry):
    raw_moves = entry.get("moves", [])
    moves = [
        Move(m["name"], m["damage"], m["energy_cost"], m.get("description", ""))
        for m in raw_moves
    ]
    return Species(
        name=entry["name"],
        health=entry["health"],
        attack=entry["attack"],
        resistance=entry["resistance"],
        is_invasive=entry["is_invasive"],
        facts=entry.get("facts", []),
        moves=moves,
        weak_to=entry.get("weak_to", []),
        strong_against=entry.get("strong_against", []),
    )


# This function loads all species from both the defenders and invaders JSON files and returns
# them as a single combined list of Species objects, silently skipping any file that doesn't exist
def load_species(natives_path="data/defenders.json", invaders_path="data/invaders_set_alpha.json"):
    species_list = []
    for path in (natives_path, invaders_path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                species_list.append(_species_from_entry(entry))
        except FileNotFoundError:
            pass
    return species_list


# This function loads native defenders from the JSON file and returns them as Species objects
# in the same order as the provided names list, used to maintain consistent display ordering
# on the roster and team selection screens
def load_defender_natives_ordered(names: list[str], natives_path="data/defenders.json"):
    try:
        with open(natives_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    by_name = {e["name"]: e for e in data if not e.get("is_invasive", False)}
    out = []
    for n in names:
        e = by_name.get(n)
        if e:
            out.append(_species_from_entry(e))
    return out


# This function generates an invader wave for the given wave number by loading invaders directly
# from the JSON file and randomly sampling from them, falling back to the all_species list if
# the file doesn't exist
# The number of invaders and the difficulty multiplier both scale up with the wave number
def generate_wave(wave_num, all_species):
    invaders_path = "data/invaders_set_alpha.json"
    try:
        with open(invaders_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        invaders = [_species_from_entry(e) for e in data]
    except FileNotFoundError:
        invaders = []
    if not invaders:
        invaders = [s for s in all_species if s.is_invasive]

    difficulty = round(1.0 + (wave_num - 1) * 0.2, 2)
    num_invaders = 1 + (wave_num - 1) // 3
    num_invaders = min(num_invaders, len(invaders))
    selected = random.sample(invaders, num_invaders)
    return Wave(wave_num=wave_num, invaders=selected, difficulty=difficulty)


# This function looks up a raw entity name in an optional display name map and returns
# the mapped display name if found, or the raw name unchanged if not
def _display_entity_name(raw_name: str, name_map: dict[str, str] | None) -> str:
    if name_map and raw_name in name_map:
        return name_map[raw_name]
    return raw_name


# This function replaces the defender slug prefix in a raw move name with the card display name
# so move labels shown in the battle log use the proper formatted name instead of the slug
# For example "nene Move 2" becomes "Nēnē Move 2"
def _display_move_name(raw_move_name: str, defender_slug: str, defender_label: str) -> str:
    base_variants = {
        defender_slug,
        defender_slug.replace("_", " "),
        defender_slug.replace("-", " "),
    }
    prefixes = base_variants | {v.title() for v in base_variants}
    for prefix in prefixes:
        prefix_with_space = f"{prefix} "
        if raw_move_name.startswith(prefix_with_space):
            return f"{defender_label} {raw_move_name[len(prefix_with_space):]}"
    return raw_move_name


# This function builds and returns the initial battle state dict from the selected team names,
# the generated wave, and the chosen difficulty setting
# It applies health and attack multipliers to invaders based on difficulty, sets starting energy
# to 5 with a cap of 10 and regen of 3 per turn, and initializes all analytics tracking fields
def init_battle(
    team_names,
    wave,
    all_species,
    difficulty="normal",
):
    settings = DIFFICULTY_SETTINGS.get(difficulty, DIFFICULTY_SETTINGS["normal"])
    health_mult = settings["health_mult"]
    attack_mult = settings["attack_mult"]

    species_map = {s.name: s for s in all_species}

    team = [
        {"name": n, "hp": species_map[n].health, "max_hp": species_map[n].health}
        for n in team_names
        if n in species_map
    ]

    invaders = [
        {
            "name": inv.name,
            "hp": max(1, int(inv.health * health_mult)),
            "max_hp": max(1, int(inv.health * health_mult)),
            "weak_to": inv.weak_to,
            "strong_against": inv.strong_against,
        }
        for inv in wave.invaders
    ]

    return {
        "wave_num": wave.wave_num,
        "difficulty": wave.difficulty,
        "team": team,
        "active_idx": 0,
        "invaders": invaders,
        "invader_idx": 0,
        "attack_mult": attack_mult,
        "energy": 5,
        "max_energy": 10,
        "energy_regen": 3,
        "turn": 1,
        "log": [],
        "battle_over": False,
        "player_won": False,
        "analytics": {
            "turns_taken": 0,
            "total_damage_dealt": 0,
            "total_damage_taken": 0,
            "max_damage_received": 0,
            "energy_spent": 0,
            "invaders_defeated": 0,
            "defenders_fainted": 0,
            "max_single_hit": 0,
            "move_usage": {},
            "defender_usage": {},
        },
    }


# This function resolves a single player turn by applying the chosen move's damage to the current
# invader, then having the invader counter-attack the active defender if it's still alive
# It updates all analytics fields, advances the invader or defender index if either faints,
# sets battle_over and player_won accordingly, regenerates energy if the battle continues,
# and appends log messages trimmed to the last 8 entries
# The function mutates battle_state in place and no-ops if the move is invalid or unaffordable
def process_turn(
    battle_state,
    move_name,
    all_species,
    defender_name_map: dict[str, str] | None = None,
    invader_name_map: dict[str, str] | None = None,
):
    species_map = {s.name: s for s in all_species}

    active = battle_state["team"][battle_state["active_idx"]]
    active_species = species_map[active["name"]]

    inv_state = battle_state["invaders"][battle_state["invader_idx"]]
    inv_species = species_map.get(inv_state["name"])

    # Find and validate the chosen move
    move = next((m for m in active_species.moves if m.name == move_name), None)
    if move is None or move.energy_cost > battle_state["energy"]:
        return

    log = []

    analytics = battle_state.setdefault("analytics", {})
    analytics.setdefault("move_usage", {})
    analytics.setdefault("defender_usage", {})
    defender_name_map = defender_name_map or {}
    invader_name_map = invader_name_map or {}
    active_name_display = _display_entity_name(active["name"], defender_name_map)
    invader_name_display = _display_entity_name(inv_state["name"], invader_name_map)
    move_display = _display_move_name(move.name, active["name"], active_name_display)
    analytics["turns_taken"] = analytics.get("turns_taken", 0) + 1
    analytics["defender_usage"][active["name"]] = (
        analytics["defender_usage"].get(active["name"], 0) + 1
    )

    # Player attacks
    inv_hp_before = inv_state["hp"]
    battle_state["energy"] -= move.energy_cost
    inv_state["hp"] = max(0, inv_state["hp"] - move.damage)
    actual_player_damage = inv_hp_before - inv_state["hp"]
    analytics["total_damage_dealt"] = analytics.get("total_damage_dealt", 0) + actual_player_damage
    analytics["energy_spent"] = analytics.get("energy_spent", 0) + move.energy_cost
    analytics["max_single_hit"] = max(analytics.get("max_single_hit", 0), actual_player_damage)
    analytics["move_usage"][move.name] = analytics["move_usage"].get(move.name, 0) + 1
    log.append(f"{active_name_display} used {move_display} — {move.damage} damage!")

    # Invader counter-attacks if still alive
    if inv_state["hp"] > 0 and inv_species:
        inv_dmg = int(inv_species.attack * battle_state["difficulty"] * battle_state.get("attack_mult", 1.0))
        active_hp_before = active["hp"]
        active["hp"] = max(0, active["hp"] - inv_dmg)
        actual_invader_damage = active_hp_before - active["hp"]
        analytics["total_damage_taken"] = analytics.get("total_damage_taken", 0) + actual_invader_damage
        analytics["max_damage_received"] = max(
            analytics.get("max_damage_received", 0), actual_invader_damage
        )
        log.append(f"{invader_name_display} struck back for {inv_dmg} damage!")

    # Check: invader fainted
    if inv_state["hp"] <= 0:
        log.append(f"{invader_name_display} was defeated!")
        analytics["invaders_defeated"] = analytics.get("invaders_defeated", 0) + 1
        battle_state["invader_idx"] += 1
        if battle_state["invader_idx"] >= len(battle_state["invaders"]):
            battle_state["battle_over"] = True
            battle_state["player_won"] = True

    # Check: active defender fainted
    if active["hp"] <= 0:
        log.append(f"{active_name_display} fainted!")
        analytics["defenders_fainted"] = analytics.get("defenders_fainted", 0) + 1
        battle_state["active_idx"] += 1
        if battle_state["active_idx"] >= len(battle_state["team"]):
            battle_state["battle_over"] = True
            battle_state["player_won"] = False

    # Regen energy for next turn (only if battle continues)
    if not battle_state["battle_over"]:
        battle_state["energy"] = min(
            battle_state["max_energy"],
            battle_state["energy"] + battle_state["energy_regen"]
        )
        battle_state["turn"] += 1

    # Keep log to last 8 entries
    battle_state["log"] = (battle_state["log"] + log)[-8:]


# This function calculates and returns the points earned for winning a wave based on the wave
# number and the total remaining HP across the player's team, returning 0 if the player lost
def score_for_wave(battle_state):
    if not battle_state["player_won"]:
        return 0
    remaining_hp = sum(m["hp"] for m in battle_state["team"])
    return 100 * battle_state["wave_num"] + remaining_hp