"""
tests.py — Kia'i 'Aina Test Suite
Run with:  python -m pytest tests.py -v
       or: python -m unittest tests.py -v
"""

import json
import unittest
from pathlib import Path

from app import app, WAVE_LIMITS
from game_logic import (
    DIFFICULTY_SETTINGS,
    generate_wave,
    init_battle,
    load_invaders,
    load_species,
    process_turn,
    score_for_wave,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent / "data"


def _make_client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-key"
    return app.test_client()


def _start_session(client, difficulty="normal"):
    """Push minimal session state so game routes don't redirect to home."""
    with client.session_transaction() as sess:
        sess["wave_num"] = 1
        sess["score"] = 0
        sess["waves_completed"] = 0
        sess["run_history"] = []
        sess["difficulty"] = difficulty


# ---------------------------------------------------------------------------
# 1. Page / Route Tests
# ---------------------------------------------------------------------------

class TestPages(unittest.TestCase):
    """
    WHY: Verify every public page returns HTTP 200 and doesn't crash on load.
    A broken import, missing template, or bad route will surface here before
    any gameplay logic is tested.
    """

    def setUp(self):
        self.client = _make_client()

    def test_home_page_loads(self):
        """Home page should always be accessible."""
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)

    def test_difficulty_page_loads(self):
        """Difficulty select page should load without a session."""
        r = self.client.get("/difficulty")
        self.assertEqual(r.status_code, 200)

    def test_leaderboard_page_loads(self):
        """Leaderboard page should load even when empty."""
        r = self.client.get("/leaderboard")
        self.assertEqual(r.status_code, 200)

    def test_compendium_page_loads(self):
        """Compendium page should load and show species data."""
        r = self.client.get("/compendium")
        self.assertEqual(r.status_code, 200)

    def test_game_redirects_without_session(self):
        """
        /game requires an active session. Without one the user should be
        redirected to home rather than seeing an error.
        """
        r = self.client.get("/game")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/", r.headers["Location"])

    def test_battle_redirects_without_session(self):
        """/battle should redirect to home when no battle is in progress."""
        r = self.client.get("/battle")
        self.assertEqual(r.status_code, 302)

    def test_result_redirects_without_session(self):
        """/result should redirect to home when no battle state exists."""
        r = self.client.get("/result")
        self.assertEqual(r.status_code, 302)

    def test_start_post_sets_difficulty_and_redirects(self):
        """
        POSTing to /start should store the chosen difficulty in the session
        and redirect to /game.
        """
        r = self.client.post("/start", data={"difficulty": "hard"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("game", r.headers["Location"])

    def test_game_page_loads_with_session(self):
        """
        Once a session is active the team-select screen should return 200.
        """
        _start_session(self.client)
        r = self.client.get("/game")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 2. Difficulty Settings Tests
# ---------------------------------------------------------------------------

class TestDifficultySettings(unittest.TestCase):
    """
    WHY: The difficulty cards advertise specific stat modifiers. These tests
    confirm that DIFFICULTY_SETTINGS contains the correct multipliers so that
    what players read on screen actually matches what happens in battle.
    """

    def test_easy_health_multiplier(self):
        """Easy mode should reduce enemy HP by 30% (multiplier = 0.7)."""
        self.assertAlmostEqual(DIFFICULTY_SETTINGS["easy"]["health_mult"], 0.7)

    def test_easy_attack_multiplier(self):
        """Easy mode should reduce enemy attack by 20% (multiplier = 0.8)."""
        self.assertAlmostEqual(DIFFICULTY_SETTINGS["easy"]["attack_mult"], 0.8)

    def test_normal_multipliers_are_baseline(self):
        """Normal mode should leave stats unchanged (multiplier = 1.0)."""
        self.assertAlmostEqual(DIFFICULTY_SETTINGS["normal"]["health_mult"], 1.0)
        self.assertAlmostEqual(DIFFICULTY_SETTINGS["normal"]["attack_mult"], 1.0)

    def test_hard_health_multiplier(self):
        """Hard mode should increase enemy HP by 30% (multiplier = 1.3)."""
        self.assertAlmostEqual(DIFFICULTY_SETTINGS["hard"]["health_mult"], 1.3)

    def test_hard_attack_multiplier(self):
        """Hard mode should increase enemy attack by 25% (multiplier = 1.25)."""
        self.assertAlmostEqual(DIFFICULTY_SETTINGS["hard"]["attack_mult"], 1.25)

    def test_infinite_health_multiplier(self):
        """Infinite mode should increase enemy HP by 50% (multiplier = 1.5)."""
        self.assertAlmostEqual(DIFFICULTY_SETTINGS["infinite"]["health_mult"], 1.5)

    def test_infinite_attack_multiplier(self):
        """Infinite mode should increase enemy attack by 40% (multiplier = 1.4)."""
        self.assertAlmostEqual(DIFFICULTY_SETTINGS["infinite"]["attack_mult"], 1.4)

    def test_easy_enemy_hp_is_lower_than_normal(self):
        """
        When a battle is initialised, Easy invaders must have less HP than
        the same invaders on Normal.
        """
        all_species = load_species()
        wave = generate_wave(1, all_species)
        easy_state = init_battle(
            [all_species[0].name], wave, all_species, difficulty="easy"
        )
        normal_state = init_battle(
            [all_species[0].name], wave, all_species, difficulty="normal"
        )
        easy_hp = easy_state["invaders"][0]["max_hp"]
        normal_hp = normal_state["invaders"][0]["max_hp"]
        self.assertLess(easy_hp, normal_hp)

    def test_infinite_enemy_hp_is_higher_than_normal(self):
        """Infinite invaders must have more HP than Normal invaders."""
        all_species = load_species()
        wave = generate_wave(1, all_species)
        inf_state = init_battle(
            [all_species[0].name], wave, all_species, difficulty="infinite"
        )
        normal_state = init_battle(
            [all_species[0].name], wave, all_species, difficulty="normal"
        )
        self.assertGreater(
            inf_state["invaders"][0]["max_hp"],
            normal_state["invaders"][0]["max_hp"],
        )

    def test_attack_mult_stored_in_battle_state(self):
        """
        The attack multiplier must be persisted in the battle state so
        process_turn can apply it on every enemy counter-attack.
        """
        all_species = load_species()
        wave = generate_wave(1, all_species)
        state = init_battle(
            [all_species[0].name], wave, all_species, difficulty="hard"
        )
        self.assertIn("attack_mult", state)
        self.assertAlmostEqual(state["attack_mult"], 1.25)


# ---------------------------------------------------------------------------
# 3. Wave Limit Tests
# ---------------------------------------------------------------------------

class TestWaveLimits(unittest.TestCase):
    """
    WHY: Each difficulty advertises a fixed number of waves. WAVE_LIMITS must
    match those numbers, and /next must redirect to /end when the cap is hit.
    """

    def test_easy_wave_limit_is_3(self):
        self.assertEqual(WAVE_LIMITS["easy"], 3)

    def test_normal_wave_limit_is_5(self):
        self.assertEqual(WAVE_LIMITS["normal"], 5)

    def test_hard_wave_limit_is_8(self):
        self.assertEqual(WAVE_LIMITS["hard"], 8)

    def test_infinite_has_no_wave_limit(self):
        """Infinite mode must have None as its limit (no cap)."""
        self.assertIsNone(WAVE_LIMITS["infinite"])

    def test_next_wave_redirects_to_end_after_easy_limit(self):
        """
        After completing wave 3 in Easy mode, /next should send the player
        to the end screen instead of starting wave 4.
        """
        client = _make_client()
        with client.session_transaction() as sess:
            sess["wave_num"] = 3
            sess["score"] = 100
            sess["waves_completed"] = 3
            sess["run_history"] = []
            sess["difficulty"] = "easy"
            sess["game_over"] = False
        r = client.post("/next")
        self.assertEqual(r.status_code, 302)
        self.assertIn("end", r.headers["Location"])

    def test_next_wave_continues_in_infinite(self):
        """
        In Infinite mode, /next should increment the wave counter rather
        than redirect to end, no matter how high wave_num gets.
        """
        client = _make_client()
        with client.session_transaction() as sess:
            sess["wave_num"] = 20
            sess["score"] = 5000
            sess["waves_completed"] = 20
            sess["run_history"] = []
            sess["difficulty"] = "infinite"
            sess["game_over"] = False
        r = client.post("/next")
        self.assertEqual(r.status_code, 302)
        self.assertIn("game", r.headers["Location"])


# ---------------------------------------------------------------------------
# 4. Game Logic Tests
# ---------------------------------------------------------------------------

class TestGameLogic(unittest.TestCase):
    """
    WHY: The core simulation (wave generation, battle init, turn processing,
    scoring) must behave correctly independently of the web layer.
    """

    def setUp(self):
        self.all_species = load_species()
        self.natives = [s for s in self.all_species if not s.is_invasive]
        self.invaders = [s for s in self.all_species if s.is_invasive]

    def test_load_species_returns_data(self):
        """Species JSON files must load and contain at least one entry."""
        self.assertGreater(len(self.all_species), 0)

    def test_natives_and_invaders_both_present(self):
        """Both native defenders and invasive species must be loaded."""
        self.assertGreater(len(self.natives), 0)
        self.assertGreater(len(self.invaders), 0)

    def test_generate_wave_returns_invaders(self):
        """generate_wave() must return a Wave with at least one invader."""
        wave = generate_wave(1, self.all_species)
        self.assertGreater(len(wave.invaders), 0)

    def test_wave_difficulty_increases_each_wave(self):
        """
        The wave difficulty scalar must be higher on wave 3 than wave 1,
        ensuring enemies get stronger over time in all modes.
        """
        wave1 = generate_wave(1, self.all_species)
        wave3 = generate_wave(3, self.all_species)
        self.assertGreater(wave3.difficulty, wave1.difficulty)

    def test_init_battle_creates_team(self):
        """init_battle() must populate the team list from the given names."""
        wave = generate_wave(1, self.all_species)
        native = self.natives[0]
        state = init_battle([native.name], wave, self.all_species)
        self.assertEqual(len(state["team"]), 1)
        self.assertEqual(state["team"][0]["name"], native.name)

    def test_init_battle_creates_invaders(self):
        """init_battle() must include at least one invader in the state."""
        wave = generate_wave(1, self.all_species)
        state = init_battle([self.natives[0].name], wave, self.all_species)
        self.assertGreater(len(state["invaders"]), 0)

    def test_init_battle_starting_energy(self):
        """Player should start each battle with 5 energy."""
        wave = generate_wave(1, self.all_species)
        state = init_battle([self.natives[0].name], wave, self.all_species)
        self.assertEqual(state["energy"], 5)

    def test_process_turn_reduces_invader_hp(self):
        """
        Using a move must reduce the current invader's HP. This is the
        fundamental damage-dealing mechanic.
        """
        wave = generate_wave(1, self.all_species)
        native = self.natives[0]
        state = init_battle([native.name], wave, self.all_species)
        invader_hp_before = state["invaders"][0]["hp"]
        move_name = native.moves[0].name
        process_turn(state, move_name, self.all_species)
        self.assertLess(state["invaders"][0]["hp"], invader_hp_before)

    def test_process_turn_costs_energy(self):
        """Using a move must deduct its energy cost from the player's pool."""
        wave = generate_wave(1, self.all_species)
        native = self.natives[0]
        state = init_battle([native.name], wave, self.all_species)
        move = native.moves[0]
        energy_before = state["energy"]
        process_turn(state, move.name, self.all_species)
        self.assertEqual(state["energy"], energy_before - move.energy_cost + state["energy_regen"])

    def test_process_turn_blocked_by_insufficient_energy(self):
        """
        A move that costs more energy than the player has must be rejected
        — HP and energy should remain unchanged.
        """
        wave = generate_wave(1, self.all_species)
        native = self.natives[0]
        state = init_battle([native.name], wave, self.all_species)
        state["energy"] = 0
        invader_hp_before = state["invaders"][0]["hp"]
        expensive_move = max(native.moves, key=lambda m: m.energy_cost)
        process_turn(state, expensive_move.name, self.all_species)
        self.assertEqual(state["invaders"][0]["hp"], invader_hp_before)

    def test_score_is_zero_on_loss(self):
        """score_for_wave() must return 0 when the player lost."""
        wave = generate_wave(1, self.all_species)
        state = init_battle([self.natives[0].name], wave, self.all_species)
        state["battle_over"] = True
        state["player_won"] = False
        self.assertEqual(score_for_wave(state), 0)

    def test_score_is_positive_on_win(self):
        """score_for_wave() must return a positive number when player wins."""
        wave = generate_wave(1, self.all_species)
        state = init_battle([self.natives[0].name], wave, self.all_species)
        state["battle_over"] = True
        state["player_won"] = True
        self.assertGreater(score_for_wave(state), 0)

    def test_battle_log_grows_after_turn(self):
        """The battle log must contain at least one entry after a turn is played."""
        wave = generate_wave(1, self.all_species)
        native = self.natives[0]
        state = init_battle([native.name], wave, self.all_species)
        process_turn(state, native.moves[0].name, self.all_species)
        self.assertGreater(len(state["log"]), 0)


# ---------------------------------------------------------------------------
# 5. Data Integrity Tests
# ---------------------------------------------------------------------------

class TestDataIntegrity(unittest.TestCase):
    """
    WHY: The game pulls all species data from JSON files. Corrupt or
    incomplete entries would cause silent bugs in battle. These tests
    check that every species has the required fields populated.
    """

    def setUp(self):
        with open(DATA_DIR / "defenders.json", encoding="utf-8") as f:
            self.defenders = json.load(f)
        with open(DATA_DIR / "invaders_set_alpha.json", encoding="utf-8") as f:
            self.invaders = json.load(f)

    def test_six_defenders_loaded(self):
        """There should be exactly 6 native defender species."""
        self.assertEqual(len(self.defenders), 6)

    def test_six_invaders_loaded(self):
        """There should be exactly 6 invasive species."""
        self.assertEqual(len(self.invaders), 6)

    def test_all_defenders_have_three_moves(self):
        """Every defender needs exactly 3 moves for the battle UI to work."""
        for d in self.defenders:
            with self.subTest(species=d["name"]):
                self.assertEqual(len(d["moves"]), 3)

    def test_no_defender_moves_are_placeholders(self):
        """No defender move name should still say 'Move 1/2/3'."""
        for d in self.defenders:
            for m in d["moves"]:
                with self.subTest(species=d["name"], move=m["name"]):
                    self.assertNotIn("Move", m["name"])

    def test_all_defenders_have_weak_to(self):
        """Every defender must have at least one weak_to entry."""
        for d in self.defenders:
            with self.subTest(species=d["name"]):
                self.assertGreater(len(d["weak_to"]), 0)
                self.assertNotIn("Placeholder", d["weak_to"][0])

    def test_all_defenders_have_strong_against(self):
        """Every defender must have at least one strong_against entry."""
        for d in self.defenders:
            with self.subTest(species=d["name"]):
                self.assertGreater(len(d["strong_against"]), 0)
                self.assertNotIn("Placeholder", d["strong_against"][0])

    def test_all_invaders_have_weak_to(self):
        """Every invader must have at least one weak_to entry."""
        for inv in self.invaders:
            with self.subTest(species=inv["name"]):
                self.assertGreater(len(inv["weak_to"]), 0)
                self.assertNotIn("Placeholder", inv["weak_to"][0])

    def test_all_invaders_have_strong_against(self):
        """Every invader must have at least one strong_against entry."""
        for inv in self.invaders:
            with self.subTest(species=inv["name"]):
                self.assertGreater(len(inv["strong_against"]), 0)
                self.assertNotIn("Placeholder", inv["strong_against"][0])

    def test_all_species_have_positive_health(self):
        """Health must be a positive integer for all species."""
        for s in self.defenders + self.invaders:
            with self.subTest(species=s["name"]):
                self.assertGreater(s["health"], 0)

    def test_all_species_have_positive_attack(self):
        """Attack must be a positive integer for all species."""
        for s in self.defenders + self.invaders:
            with self.subTest(species=s["name"]):
                self.assertGreater(s["attack"], 0)

    def test_all_move_damage_positive(self):
        """Every move must deal at least 1 damage."""
        for d in self.defenders:
            for m in d["moves"]:
                with self.subTest(species=d["name"], move=m["name"]):
                    self.assertGreater(m["damage"], 0)

    def test_all_move_energy_costs_positive(self):
        """Every move must cost at least 1 energy."""
        for d in self.defenders:
            for m in d["moves"]:
                with self.subTest(species=d["name"], move=m["name"]):
                    self.assertGreater(m["energy_cost"], 0)


# ---------------------------------------------------------------------------
# 6. Leaderboard / Score Save Tests
# ---------------------------------------------------------------------------

class TestScoreSave(unittest.TestCase):
    """
    WHY: The save-score endpoint is the main data-persistence feature. These
    tests make sure it rejects bad input and only records infinite-mode scores.
    """

    def setUp(self):
        self.client = _make_client()

    def _post_score(self, payload, difficulty="infinite"):
        with self.client.session_transaction() as sess:
            sess["score"] = 999
            sess["difficulty"] = difficulty
            sess["run_history"] = [{}]
        return self.client.post(
            "/save-score",
            json=payload,
            content_type="application/json",
        )

    def test_save_score_requires_player_name(self):
        """Submitting without a name must be rejected with 400."""
        r = self._post_score({"player_name": "", "email": ""})
        self.assertEqual(r.status_code, 400)

    def test_save_score_rejects_invalid_email(self):
        """A supplied email that has no '@' must be rejected."""
        r = self._post_score({"player_name": "Tester", "email": "notanemail"})
        self.assertEqual(r.status_code, 400)

    def test_save_score_accepts_blank_email(self):
        """Email is optional — a blank email with a valid name must succeed."""
        r = self._post_score({"player_name": "Tester", "email": ""})
        self.assertEqual(r.status_code, 200)

    def test_save_score_only_works_for_infinite(self):
        """Non-infinite difficulty scores must be rejected (not tracked)."""
        r = self._post_score({"player_name": "Tester", "email": ""}, difficulty="normal")
        self.assertEqual(r.status_code, 400)

    def test_save_score_success_returns_json(self):
        """A valid infinite-mode save must return JSON with success=True."""
        r = self._post_score({"player_name": "Tester", "email": ""})
        data = r.get_json()
        self.assertTrue(data.get("success"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
