import json
import random
from species import Species, Wave

# Synergy bonuses: if all species in a combo are in the player's selection, apply the multiplier
# Format: { frozenset of native names : multiplier }
SYNERGY_TABLE = {
    frozenset(["nene", "pueo"]): 1.3,
    frozenset(["silversword", "ohia"]): 1.25,
}


def load_species(filepath="data/species.json"):
    with open(filepath, "r") as f:
        data = json.load(f)

    species_list = []
    for entry in data:
        s = Species(
            name=entry["name"],
            health=entry["health"],
            attack=entry["attack"],
            resistance=entry["resistance"],
            is_invasive=entry["is_invasive"],
            facts=entry.get("facts", [])
        )
        species_list.append(s)
    return species_list


def get_max_defenders(wave_num):
    if wave_num <= 2:
        return 1
    elif wave_num <= 5:
        return 2
    else:
        return 3


def generate_wave(wave_num, all_species):
    invaders = [s for s in all_species if s.is_invasive]
    difficulty = round(1.0 + (wave_num - 1) * 0.2, 2)  # wave 1 = 1.0, wave 2 = 1.2, etc.

    # number of invaders increases every 3 waves
    num_invaders = 1 + (wave_num - 1) // 3
    num_invaders = min(num_invaders, len(invaders))

    selected_invaders = random.sample(invaders, num_invaders)
    return Wave(wave_num=wave_num, invaders=selected_invaders, difficulty=difficulty)


def calculate_battle(native, invader, difficulty):
    native_power = native.attack * native.get_resistance_against(invader.name)
    invader_power = invader.attack * difficulty

    winner = "native" if native_power >= invader_power else "invader"

    return {
        "native": native.name,
        "invader": invader.name,
        "native_power": round(native_power, 2),
        "invader_power": round(invader_power, 2),
        "winner": winner
    }


def check_synergy(native_list):
    names = set(s.name for s in native_list)
    bonus = 1.0
    triggered = []

    for combo, multiplier in SYNERGY_TABLE.items():
        if combo.issubset(names):
            bonus *= multiplier
            triggered.append((list(combo), multiplier))

    return bonus, triggered


def resolve_wave(native_list, wave):
    synergy_bonus, triggered_synergies = check_synergy(native_list)
    matchups = []
    native_wins = 0
    invader_wins = 0

    for invader in wave.invaders:
        best_result = None
        for native in native_list:
            result = calculate_battle(native, invader, wave.difficulty)
            # apply synergy bonus to native power
            result["native_power"] = round(result["native_power"] * synergy_bonus, 2)
            result["winner"] = "native" if result["native_power"] >= result["invader_power"] else "invader"
            # keep the best native matchup against this invader
            if best_result is None or result["native_power"] > best_result["native_power"]:
                best_result = result
        matchups.append(best_result)
        if best_result["winner"] == "native":
            native_wins += 1
        else:
            invader_wins += 1

    wave_won = native_wins >= invader_wins

    return {
        "wave_num": wave.wave_num,
        "difficulty": wave.difficulty,
        "matchups": matchups,
        "native_wins": native_wins,
        "invader_wins": invader_wins,
        "wave_won": wave_won,
        "synergy_bonus": round(synergy_bonus, 2),
        "triggered_synergies": triggered_synergies
    }


def update_score(wave_result, current_score):
    if wave_result["wave_won"]:
        points = 100 * wave_result["wave_num"] + int((wave_result["synergy_bonus"] - 1.0) * 200)
    else:
        points = 0
    return current_score + points


if __name__ == "__main__":
    all_species = load_species()

    natives = [s for s in all_species if not s.is_invasive]
    player_selection = natives[:2]

    score = 0
    for wave_num in range(1, 4):
        wave = generate_wave(wave_num, all_species)
        result = resolve_wave(player_selection, wave)
        score = update_score(result, score)

        print(f"\n--- Wave {wave_num} (difficulty {wave.difficulty}) ---")
        for m in result["matchups"]:
            print(f"  {m['native']} (power {m['native_power']}) vs {m['invader']} (power {m['invader_power']}) -> {m['winner']} wins")
        if result["triggered_synergies"]:
            print(f"  Synergy bonus: x{result['synergy_bonus']} from {result['triggered_synergies']}")
        print(f"  Wave result: {'WIN' if result['wave_won'] else 'LOSS'} | Score: {score}")
