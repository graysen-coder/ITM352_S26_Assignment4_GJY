# species.py
# This file defines the Species class to represent both native and invasive species,
# along with their attributes and interactions, also defines a wave class to contain the
# invasive species that will attack the native species in each wave of the game.
# Used Claude Sonnet 4.6 to generate initial code structure specifying name, health, attack, resistance, whether its invasive or not
# and facts about the species

class Move:
    def __init__(self, name, damage, energy_cost, description=""):
        self.name = name
        self.damage = damage
        self.energy_cost = energy_cost
        self.description = description

    def to_dict(self):
        return {
            "name": self.name,
            "damage": self.damage,
            "energy_cost": self.energy_cost,
            "description": self.description,
        }

    def __repr__(self):
        return f"Move({self.name}, dmg={self.damage}, cost={self.energy_cost})"


class Species:
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

    def get_resistance_against(self, invader_name):
        return self.resistance.get(invader_name, self.resistance.get("default", 1.0))

    def __repr__(self):
        kind = "Invasive" if self.is_invasive else "Native"
        return f"{kind}({self.name}, hp={self.health}, atk={self.attack})"


class Wave:
    def __init__(self, wave_num, invaders, difficulty):
        self.wave_num = wave_num
        self.invaders = invaders  # list of Species
        self.difficulty = difficulty

    def __repr__(self):
        return f"Wave({self.wave_num}, difficulty={self.difficulty}, invaders={self.invaders})"


if __name__ == "__main__":
    nene = Species(
        name="nene",
        health=80,
        attack=30,
        resistance={"mongoose": 1.4, "default": 1.0},
        is_invasive=False,
        facts=["The nene is Hawaii's state bird.", "Nearly went extinct in the 1950s."]
    )

    mongoose = Species(
        name="mongoose",
        health=60,
        attack=40,
        resistance={"default": 1.0},
        is_invasive=True
    )

    wave1 = Wave(wave_num=1, invaders=[mongoose], difficulty=1.0)

    print(nene)
    print(mongoose)
    print(wave1)
    print("Nene resistance vs mongoose:", nene.get_resistance_against("mongoose"))
    print("Nene resistance vs unknown:", nene.get_resistance_against("rat"))
