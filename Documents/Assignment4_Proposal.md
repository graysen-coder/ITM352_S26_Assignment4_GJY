Assignment 4 Proposal  
Kiaʻi ʻĀina \-Guardians of the Land-  
Group members: Graysen, Jadon, Yuki  
**PURPOSE**  
For our project, we want to make an educational strategy game in Python using Flask that teaches people about native species and invasive species that belong to Hawaii. While our game will be of the “tower defense” genre, it will be a wave-based strategy simulator going off of scope. It still feels like a game, but it’s more realistic for our skill level and timeline.

**MAIN FEATURES AND IMPLEMENTATION PLANS**  
The player will go through waves where invasive species “attack,” and the player chooses native species to defend each round. Different species will have values (stats) like health, attack, and resistance assigned to them. To reflect real life relationships between native and invasive species, certain combinations will yield better defense results. (We may also provide defensive synergies, methods to preserve these species, as “buffs”.)  As the waves progress, the difficulty will naturally increase where having knowledge of the relationship is crucial. During gameplay, the app will also show short facts about each species so players can learn while playing. (And perhaps a dictionary or compendium if time allows.)  
Our app will include user input through web forms and meaningful output through battle results, score/progress, and end-of-run charts. We will break the logic into functions (for wave generation, battle calculations, score updates, etc.), and use data structures like lists, dictionaries, and possibly classes for species and waves. We will also include error handling for invalid user input and file/data issues. If a login feature is necessary, we will implement one that is lightweight that allows simple profile creation via username and use Flask to link their scores to these profiles.  
**can add leaderboard**  
**make different games for different grade levels**

To cover class topics, we plan to use:

Pandas/data analysis for run history and performance stats  
Statistical charts for things like win rate and best species combinations  
File I/O for saving species data and game run data (CSV/JSON)  
Web scraping to collect species facts from [trusted websites](https://dlnr.hawaii.gov/forestry/plants/) and cache them locally  
Web app development with Flask routes and HTML templates  
For our stretch goal, we want to implement procedural wave generation with difficulty balancing, so each run has some variation akin to difficulty modes in other games.

**DIVISION OF LABOR (TBD)**  
*Core game logic member:* wave generation, battle math, resistances/synergies, and testing core functions  
*Flask/UI member*: routes, templates, forms, user flow, and input validation  
*Data/content member*: species dataset, web scraping \+ cleanup, educational content, pandas analysis, and charts

For testing, we’ll do repeated playtesting ourselves, edge-case testing (bad inputs, unusual values, missing files), and data pipeline checks (scrape \-\> save \-\> load \-\> analyze \-\> chart). If time and scheduling permits, we will either have a few friends and family or fellow ITM352 students to try it and give feedback so we can fix usability issues before final submission.

**AI IMPLEMENTATION**  
As per assignment requirement, we will use AI as a tool for development and QA acceleration, not as a FIFO code generator. We will have complete control over what we use AI to make sure it adds to the assignment as a whole rather than doing it for us so that we can be confident that we meet the assignment criteria by using our own programming decisions. We will be only using code that we understand and explain.

AI will be heavily used in areas that are beyond the scope of this assignment/course. Examples would be the integer values used for the “battles” (an intricate “rabbit hole” game devs fall into), procedural wave (or map) generation which dictates how many elements are being displayed/interacted with, game asset generation, advanced Flask integration (i.e. scaffolding, as networking is out of the scope of ITM352), and most importantly, testing the game in a multitude of ways due to human and resource limitation. We fully understand that we are MIS students and not CS students who are on the game dev track.

Overall, our goal is to build a functional and educational MIS-style tool/game that is engaging but still realistic for an intro-level project.