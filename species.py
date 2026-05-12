# ITM352 Assignment 4
# Kiai Aina: Guardians of the Land
# Names: Yuki, Jadon, Graysen
# This file defines the Species class to represent both native and invasive species,
# along with their attributes and interactions, also defines a wave class to contain the
# invasive species that will attack the native species in each wave of the game.
# There is also a move class that will represent the different moves that each species can use in battle, with their damage, attributes, and energy cost.
# Used Claude Sonnet 4.6 to generate initial code structure specifying name, health, attack, resistance, whether its invasive or not
# and facts about the species

class Move:
    # This method initializes a Move object with a name, damage value, energy cost, and an optional description that defaults to an empty string
    def __init__(self, name, damage, energy_cost, description=""):
        self.name = name
        self.damage = damage
        self.energy_cost = energy_cost
        self.description = description

    # This method returns the Move's attributes as a plain dict so it can be saved to JSON for storage in the Flask session
    def to_dict(self):
        return {
            "name": self.name,
            "damage": self.damage,
            "energy_cost": self.energy_cost,
            "description": self.description,
        }

    # This method returns a readable string representation of the Move showing its name, damage, and energy cost, used for debugging
    def __repr__(self):
        return f"Move({self.name}, dmg={self.damage}, cost={self.energy_cost})"


class Species:
    # This method initializes a Species object with its name, stats, resistance map, invasive flag,
    # facts list, moves list, and type matchup lists, defaulting all list fields to empty lists
    # if not provided to avoid mutable default argument issues
    def __init__(self, name, health, attack, resistance, is_invasive=False, facts=None, moves=None,
                 weak_to=None, strong_against=None):
        self.name = name
        self.health = health
        self.attack = attack
        self.resistance = resistance  # e.g. {"mongoose": 1.5, "default": 1.0}
        self.is_invasive = is_invasive
        self.facts = facts if facts is not None else []
        self.moves = moves if moves is not None else []
        self.weak_to = weak_to if weak_to is not None else []
        self.strong_against = strong_against if strong_against is not None else []

    # This method looks up this species' resistance multiplier against a specific invader by name,
    # falling back to the "default" resistance value if no specific entry exists
    def get_resistance_against(self, invader_name):
        return self.resistance.get(invader_name, self.resistance.get("default", 1.0))

    # This method returns a readable string representation of the Species showing whether it is
    # native or invasive, its name, HP, and attack, used for debugging
    def __repr__(self):
        kind = "Invasive" if self.is_invasive else "Native"
        return f"{kind}({self.name}, hp={self.health}, atk={self.attack})"


class Wave:
    # This method initializes a Wave object with the wave number, the list of invader Species
    # that will appear in this wave, and the difficulty multiplier for the wave
    def __init__(self, wave_num, invaders, difficulty):
        self.wave_num = wave_num
        self.invaders = invaders  # list of Species
        self.difficulty = difficulty

    # This method returns a readable string representation of the Wave showing its number,
    # difficulty, and invader list, used for debugging
    def __repr__(self):
        return f"Wave({self.wave_num}, difficulty={self.difficulty}, invaders={self.invaders})"