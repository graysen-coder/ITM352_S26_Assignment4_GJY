Kiai Aina -- Guardians of the Land

An educational wave-based strategy game built with Python and Flask that teaches players about native and invasive species in Hawaii and the interactions between them

Group Members: Graysen, Jadon, Yuki -- ITM352 Spring 2026, Assignment 4


Dependencies

flask - web app framework
jinja2 - html templating (comes with flask)
beautifulsoup4 - scraping dlnr bird data from the web
lxml - html parser for beautifulsoup
requests - making http requests for scraping
pandas - running analytics and charting data
matplotlib - creating end-of-run performance charts
seaborn - styling the charts
python-dotenv - loading .env environment variables
sendgrid - sending email notifications for the leaderboard


SETUP AND RUNNING

1. Clone or download the repository.
2. Install all libraries specified in requirements.txt
3. Start the Flask server:
       python app.py
4. Open your browser to http://127.0.0.1:5000.


HOW TO PLAY

Overview

Kiai Aina is a turn-based battle game. Each round, waves of invasive species threaten Hawaii's native ecosystem. You build a team of native Hawaiian birds to defend against them. Win waves to earn points and learn real facts about each species along the way.


Game Flow

Home -> Select Difficulty -> Pick Your Team (3 defenders) -> Battle -> Wave Results -> Next Wave -> ... -> End Screen


1. Home Screen

The landing page. Click Play to start a new game or browse the Compendium to study species before playing.


2. Difficulty Selection

Choose one of four difficulty modes:

- Easy: 3 waves, Invader HP 0.7x, Invader Attack 0.8x
- Normal: 5 waves, Invader HP 1.0x, Invader Attack 1.0x
- Hard: 8 waves, Invader HP 1.3x, Invader Attack 1.25x
- Infinite: Endless waves, Invader HP 1.5x, Invader Attack 1.4x

Note: Only Infinite mode scores are saved to the leaderboard.


3. Team Selection

Pick up to 3 native Hawaiian bird defenders from the roster. Review each defender's stats, strengths, and weaknesses before committing.

Defenders (Native Hawaiian Birds):

- Nene: HP 80, Attack 30, Strong Against: Coqui Frog, Naio Thrips, Weak To: Mongoose, Little Fire Ant
- 'I'iwi: HP 56, Attack 24, Strong Against: Naio Thrips, Coqui Frog, Weak To: Brown Tree Snake, Little Fire Ant
- 'Io: HP 72, Attack 38, Strong Against: Mongoose, Brown Tree Snake, Weak To: Little Fire Ant, Coconut Rhinoceros Beetle
- Pueo: HP 70, Attack 36, Strong Against: Mongoose, Coqui Frog, Weak To: Brown Tree Snake, Little Fire Ant
- 'Ua'u: HP 60, Attack 28, Strong Against: Coqui Frog, Naio Thrips, Weak To: Mongoose, Little Fire Ant
- 'Alala: HP 64, Attack 32, Strong Against: Coconut Rhinoceros Beetle, Coqui Frog, Weak To: Mongoose, Brown Tree Snake


4. Battle

Each battle is turn-based. Your active defender fights one invader at a time.

Energy System:
- You start each wave with 5 energy (max 10).
- Each turn you gain 3 energy (regen).
- Moves cost energy -- choose wisely.

Each Defender Has 3 Moves:

Basic move  | Energy Cost: 1 | Damage: Low
Medium move | Energy Cost: 3 | Damage: Medium
Power move  | Energy Cost: 5 | Damage: High

Turn Sequence:
1. You choose a move for your active defender.
2. Your defender attacks the current invader.
3. If the invader is still alive, it counter-attacks your defender.
4. If an invader's HP reaches 0, the next invader enters.
5. If your active defender faints, the next team member steps up.
6. The wave ends when all invaders are defeated (win) or all your defenders faint (loss).

Invader difficulty scales with wave number -- later waves have more invaders and higher base difficulty.


5. Wave Results

After each battle you see:
- Win/loss outcome
- Per-wave analytics (turns taken, damage dealt/taken, energy spent, invaders defeated)
- Educational facts about the invaders you just faced (randomly sampled from real data)

Click Next Wave to continue or return home if the run is over.


6. End Screen

After all waves are complete (or after a loss), you see a full run summary:
- Total score, waves won/lost, win rate
- Damage trends and points-per-wave charts (generated with matplotlib/pandas)
- Overall stats: best wave, most-used defender, total invaders defeated

Infinite mode only: Enter your name and email to submit your score to the leaderboard. Players whose scores get beaten receive an email notification via SendGrid.


SCORING

Points per wave = (100 x wave_number) + remaining team HP

You only earn points for waves you win. Surviving with more HP = higher score.


COMPENDIUM

You can browse all defenders and invaders, their stats, scientific names, habitat info, and DLNR species profile links before or after a run at the species compendium.


LEADERBOARD

View the top 10 Infinite mode scores at /leaderboard. All new plays get offered a spot on the leaderboard until 10 scores are saved, at that point a user would only be offered a spot on the leaderboard if they beat one of the scores already on it. Scores are stored in data/leaderboard.json and ranked by total points.


PROJECT STRUCTURE

app.py               - Flask routes and session logic
game_logic.py        - Battle engine: wave generation, turn processing, and scoring
species.py           - Species, Wave, and Move data classes
defender_cards.py    - DLNR web scraper for native bird metadata
invader_cards.py     - Invader card loader from JSON
build_invaders_set_1.py - Script to build invader data
tests.py             - Test suite
requirements.txt     - Python dependencies
data/                - JSON files for species stats, leaderboard scores, and game data
    defenders.json         - Native bird stats and moves
    invaders_set_alpha.json - Invasive species stats and educational content
    leaderboard.json       - Infinite mode high scores
static/              - Background image, title graphic, and species photos
templates/           - HTML templates for each screen


DATA SOURCES

Species facts and profiles are sourced from Hawaii DLNR Wildlife -- Native Birds:
https://dlnr.hawaii.gov/wildlife/birds/