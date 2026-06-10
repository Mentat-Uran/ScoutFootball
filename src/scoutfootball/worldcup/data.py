"""Static data for the 2026 FIFA World Cup (US/Canada/Mexico).

48 teams, 12 groups (A-L), June 11 - July 19 2026.
Group and squad data are built-in; match schedules are generated from the
official fixture pattern.  Squad rosters are placeholder lists of likely
call-ups based on recent national team selections — they will be updated
once official 26-man squads are announced.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Groups ────────────────────────────────────────────────────────────────

GROUPS: dict[str, list[str]] = {
    "A": ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curacao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

# Mapping: national team name -> common club-league country for rating lookup
# Players from these countries' domestic leagues are likely in our FBref data.
NATIONALITY_TO_LEAGUE_COUNTRY: dict[str, list[str]] = {
    "Mexico": ["MEX"],
    "South Africa": ["RSA"],
    "South Korea": ["KOR"],
    "Czech Republic": ["CZE"],
    "Canada": ["CAN"],
    "Bosnia and Herzegovina": ["BIH"],
    "Qatar": ["QAT"],
    "Switzerland": ["SUI"],
    "Brazil": ["BRA"],
    "Morocco": ["MAR"],
    "Haiti": ["HAI"],
    "Scotland": ["SCO"],
    "United States": ["USA"],
    "Paraguay": ["PAR"],
    "Australia": ["AUS"],
    "Turkey": ["TUR"],
    "Germany": ["GER"],
    "Curacao": ["CUW"],
    "Ivory Coast": ["CIV"],
    "Ecuador": ["ECU"],
    "Netherlands": ["NED"],
    "Japan": ["JPN"],
    "Sweden": ["SWE"],
    "Tunisia": ["TUN"],
    "Belgium": ["BEL"],
    "Egypt": ["EGY"],
    "Iran": ["IRN"],
    "New Zealand": ["NZL"],
    "Spain": ["ESP"],
    "Cape Verde": ["CPV"],
    "Saudi Arabia": ["KSA"],
    "Uruguay": ["URU"],
    "France": ["FRA"],
    "Senegal": ["SEN"],
    "Iraq": ["IRQ"],
    "Norway": ["NOR"],
    "Argentina": ["ARG"],
    "Algeria": ["ALG"],
    "Austria": ["AUT"],
    "Jordan": ["JOR"],
    "Portugal": ["POR"],
    "DR Congo": ["COD"],
    "Uzbekistan": ["UZB"],
    "Colombia": ["COL"],
    "England": ["ENG"],
    "Croatia": ["CRO"],
    "Ghana": ["GHA"],
    "Panama": ["PAN"],
}

# FIFA country codes (3-letter)
FIFA_CODES: dict[str, str] = {
    "Mexico": "MEX", "South Africa": "RSA", "South Korea": "KOR",
    "Czech Republic": "CZE", "Canada": "CAN",
    "Bosnia and Herzegovina": "BIH", "Qatar": "QAT", "Switzerland": "SUI",
    "Brazil": "BRA", "Morocco": "MAR", "Haiti": "HAI", "Scotland": "SCO",
    "United States": "USA", "Paraguay": "PAR", "Australia": "AUS",
    "Turkey": "TUR", "Germany": "GER", "Curacao": "CUW",
    "Ivory Coast": "CIV", "Ecuador": "ECU", "Netherlands": "NED",
    "Japan": "JPN", "Sweden": "SWE", "Tunisia": "TUN",
    "Belgium": "BEL", "Egypt": "EGY", "Iran": "IRN",
    "New Zealand": "NZL", "Spain": "ESP", "Cape Verde": "CPV",
    "Saudi Arabia": "KSA", "Uruguay": "URU", "France": "FRA",
    "Senegal": "SEN", "Iraq": "IRQ", "Norway": "NOR",
    "Argentina": "ARG", "Algeria": "ALG", "Austria": "AUT",
    "Jordan": "JOR", "Portugal": "POR", "DR Congo": "COD",
    "Uzbekistan": "UZB", "Colombia": "COL", "England": "ENG",
    "Croatia": "CRO", "Ghana": "GHA", "Panama": "PAN",
}

# Host countries
HOSTS = ["United States", "Canada", "Mexico"]

# Tournament dates
TOURNAMENT_START = "2026-06-11"
TOURNAMENT_END = "2026-07-19"

# Opta supercomputer predicted win probabilities (top 10, from public reports).
# Kept as a reference prior; actual team strengths are now computed from
# squad ratings via compute_team_strengths().
OPTA_WIN_PROBABILITY: dict[str, float] = {
    "Spain": 0.161, "France": 0.128, "Brazil": 0.112,
    "England": 0.098, "Argentina": 0.087, "Germany": 0.072,
    "Portugal": 0.065, "Netherlands": 0.054, "Uruguay": 0.038,
    "Belgium": 0.032,
}

# Backward-compatible alias
WIN_PROBABILITY = OPTA_WIN_PROBABILITY


# ── Match schedule ────────────────────────────────────────────────────────

@dataclass
class Match:
    """A single World Cup match."""
    matchday: int
    date: str  # YYYY-MM-DD
    time_et: str  # Eastern Time HH:MM
    home: str
    away: str
    venue: str
    city: str
    group: str | None = None  # None for knockout
    stage: str = "Group Stage"


def generate_group_stage_matches() -> list[Match]:
    """Generate all 72 group-stage matches (12 groups x 6 matches each).

    Uses the official 2026 World Cup fixture pattern:
    - Each group plays 3 matchdays
    - Matchday 1: Team1 vs Team2, Team3 vs Team4
    - Matchday 2: Team1 vs Team3, Team2 vs Team4
    - Matchday 3: Team1 vs Team4, Team2 vs Team3

    Dates are approximate placeholders based on the official schedule
    pattern (June 11-26 for group stage). Exact times/venues will be
    updated from FIFA's official fixture list.
    """
    matches: list[Match] = []
    # Base date for group stage: June 11
    # Each group's 3 matchdays are spread across ~2 weeks
    # Groups A-D start June 11, E-H start June 12, I-L start June 13
    group_start_offsets = {
        "A": 0, "B": 0, "C": 0, "D": 0,
        "E": 1, "F": 1, "G": 1, "H": 1,
        "I": 2, "J": 2, "K": 2, "L": 2,
    }
    matchday_gaps = [0, 4, 8]  # days between matchdays within a group

    # Venue assignments (simplified — each group is primarily at one venue cluster)
    group_venues: dict[str, tuple[str, str]] = {
        "A": ("Estadio Azteca", "Mexico City"),
        "B": ("BMO Field", "Toronto"),
        "C": ("SoFi Stadium", "Los Angeles"),
        "D": ("AT&T Stadium", "Arlington"),
        "E": ("MetLife Stadium", "New York"),
        "F": ("Lumen Field", "Seattle"),
        "G": ("Mercedes-Benz Stadium", "Atlanta"),
        "H": ("Hard Rock Stadium", "Miami"),
        "I": ("Gillette Stadium", "Boston"),
        "J": ("NRG Stadium", "Houston"),
        "K": ("Levi's Stadium", "San Francisco"),
        "L": ("Lincoln Financial Field", "Philadelphia"),
    }

    for group_letter, teams in GROUPS.items():
        offset = group_start_offsets[group_letter]
        venue, city = group_venues[group_letter]
        t1, t2, t3, t4 = teams

        for md_idx, gap in enumerate(matchday_gaps):
            day = 11 + offset + gap
            month = 6
            if day > 30:
                month = 7
                day -= 30
            date_str = f"2026-{month:02d}-{day:02d}"

            if md_idx == 0:
                pairings = [(t1, t2), (t3, t4)]
            elif md_idx == 1:
                pairings = [(t1, t3), (t2, t4)]
            else:
                pairings = [(t1, t4), (t2, t3)]

            for game_idx, (home, away) in enumerate(pairings):
                time_et = "19:30" if game_idx == 0 else "22:00"
                matches.append(Match(
                    matchday=md_idx + 1,
                    date=date_str,
                    time_et=time_et,
                    home=home,
                    away=away,
                    venue=venue,
                    city=city,
                    group=group_letter,
                    stage="Group Stage",
                ))

    return matches


# ── Squad data (placeholder) ──────────────────────────────────────────────

@dataclass
class SquadPlayer:
    """A player in a World Cup squad."""
    name: str
    position: str  # GK/CB/FB/DM/CM/AM/W/ST
    club: str
    club_league: str  # League where the player's club plays
    has_rating: bool = False
    rating: float | None = None
    rating_confidence: str = "none"  # high/medium/low/none


# Placeholder squads — key players likely to be called up.
# This is a curated list of ~15-20 notable players per major team.
# Full 26-man squads will be updated once officially announced.
# Players marked with club_league containing "Big5" are likely in our rating data.

SQUADS: dict[str, list[dict]] = {
    "Argentina": [
        {"name": "Lionel Messi", "position": "AM", "club": "Inter Miami", "club_league": "MLS"},
        {"name": "Julian Alvarez", "position": "ST", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Lautaro Martinez", "position": "ST", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Angel Di Maria", "position": "W", "club": "Benfica", "club_league": "Liga Portugal"},
        {"name": "Rodrigo De Paul", "position": "CM", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Enzo Fernandez", "position": "CM", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Alexis Mac Allister", "position": "CM", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Emiliano Martinez", "position": "GK", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Cristian Romero", "position": "CB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Nahuel Molina", "position": "FB", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Nicolas Otamendi", "position": "CB", "club": "Benfica", "club_league": "Liga Portugal"},
        {"name": "Leandro Paredes", "position": "DM", "club": "Roma", "club_league": "Serie A"},
        {"name": "Nicolas Tagliafico", "position": "FB", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Gonzalo Montiel", "position": "FB", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Paulo Dybala", "position": "AM", "club": "Roma", "club_league": "Serie A"},
    ],
    "Brazil": [
        {"name": "Neymar", "position": "W", "club": "Santos", "club_league": "Brasileirao"},
        {"name": "Vinicius Junior", "position": "W", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Rodrygo", "position": "W", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Raphinha", "position": "W", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Bruno Guimaraes", "position": "CM", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Casemiro", "position": "DM", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Marquinhos", "position": "CB", "club": "PSG", "club_league": "Ligue 1"},
        {"name": "Alisson", "position": "GK", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Danilo", "position": "FB", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Gabriel Magalhaes", "position": "CB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Endrick", "position": "ST", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Lucas Paqueta", "position": "AM", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Eder Militao", "position": "CB", "club": "Real Madrid", "club_league": "La Liga"},
    ],
    "France": [
        {"name": "Kylian Mbappe", "position": "ST", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Ousmane Dembele", "position": "W", "club": "PSG", "club_league": "Ligue 1"},
        {"name": "Antoine Griezmann", "position": "AM", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Aurelien Tchouameni", "position": "DM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Eduardo Camavinga", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Mike Maignan", "position": "GK", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Theo Hernandez", "position": "FB", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Dayot Upamecano", "position": "CB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Jules Kounde", "position": "FB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "N'Golo Kante", "position": "DM", "club": "Ittihad", "club_league": "SPL"},
        {"name": "Olivier Giroud", "position": "ST", "club": "Lille", "club_league": "Ligue 1"},
        {"name": "William Saliba", "position": "CB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Kingsley Coman", "position": "W", "club": "Bayern Munich", "club_league": "Bundesliga"},
    ],
    "England": [
        {"name": "Harry Kane", "position": "ST", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Jude Bellingham", "position": "AM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Phil Foden", "position": "W", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Bukayo Saka", "position": "W", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Declan Rice", "position": "DM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Jordan Pickford", "position": "GK", "club": "Everton", "club_league": "Premier League"},
        {"name": "John Stones", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Kyle Walker", "position": "FB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Cole Palmer", "position": "AM", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Trent Alexander-Arnold", "position": "FB", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Marcus Rashford", "position": "W", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Harry Maguire", "position": "CB", "club": "Manchester United", "club_league": "Premier League"},
    ],
    "Germany": [
        {"name": "Jamal Musiala", "position": "AM", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Florian Wirtz", "position": "AM", "club": "Bayer Leverkusen", "club_league": "Bundesliga"},
        {"name": "Ilkay Gundogan", "position": "CM", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Joshua Kimmich", "position": "DM", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Manuel Neuer", "position": "GK", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Antonio Rudiger", "position": "CB", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Nico Schlotterbeck", "position": "CB", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
        {"name": "Kai Havertz", "position": "ST", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Leroy Sane", "position": "W", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Serge Gnabry", "position": "W", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Jonathan Tah", "position": "CB", "club": "Bayer Leverkusen", "club_league": "Bundesliga"},
    ],
    "Spain": [
        {"name": "Lamine Yamal", "position": "W", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Pedri", "position": "CM", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Rodri", "position": "DM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Dani Olmo", "position": "AM", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Unai Simon", "position": "GK", "club": "Athletic Bilbao", "club_league": "La Liga"},
        {"name": "Aymeric Laporte", "position": "CB", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Ferran Torres", "position": "W", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Alvaro Morata", "position": "ST", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Gavi", "position": "CM", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Marc Cucurella", "position": "FB", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Robin Le Normand", "position": "CB", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Nico Williams", "position": "W", "club": "Athletic Bilbao", "club_league": "La Liga"},
    ],
    "Portugal": [
        {"name": "Cristiano Ronaldo", "position": "ST", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Bruno Fernandes", "position": "AM", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Bernardo Silva", "position": "W", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Ruben Dias", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Diogo Jota", "position": "ST", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Rafael Leao", "position": "W", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Joao Cancelo", "position": "FB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Pepe", "position": "CB", "club": "Porto", "club_league": "Liga Portugal"},
        {"name": "Vitinha", "position": "CM", "club": "PSG", "club_league": "Ligue 1"},
        {"name": "Diogo Costa", "position": "GK", "club": "Porto", "club_league": "Liga Portugal"},
    ],
    "Netherlands": [
        {"name": "Virgil van Dijk", "position": "CB", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Frenkie de Jong", "position": "CM", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Cody Gakpo", "position": "W", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Xavi Simons", "position": "AM", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Memphis Depay", "position": "ST", "club": "Corinthians", "club_league": "Brasileirao"},
        {"name": "Matthijs de Ligt", "position": "CB", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Denzel Dumfries", "position": "FB", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Ronald Araujo", "position": "CB", "club": "Barcelona", "club_league": "La Liga"},
    ],
    "Italy": [],  # Did not qualify
    "Uruguay": [
        {"name": "Darwin Nunez", "position": "ST", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Federico Valverde", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Ronald Araujo", "position": "CB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Jose Gimenez", "position": "CB", "club": "Atletico Madrid", "club_league": "La Liga"},
    ],
    "Croatia": [
        {"name": "Luka Modric", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Mateo Kovacic", "position": "CM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Joško Gvardiol", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Ivan Perisic", "position": "W", "club": "PSV", "club_league": "Eredivisie"},
    ],
    "Belgium": [
        {"name": "Kevin De Bruyne", "position": "AM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Romelu Lukaku", "position": "ST", "club": "Napoli", "club_league": "Serie A"},
        {"name": "Thibaut Courtois", "position": "GK", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Youri Tielemans", "position": "CM", "club": "Aston Villa", "club_league": "Premier League"},
    ],
    "United States": [
        {"name": "Christian Pulisic", "position": "W", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Weston McKennie", "position": "CM", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Giovanni Reyna", "position": "AM", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
        {"name": "Matt Turner", "position": "GK", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Antonee Robinson", "position": "FB", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Yunus Musah", "position": "CM", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Folarin Balogun", "position": "ST", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Tim Weah", "position": "W", "club": "Juventus", "club_league": "Serie A"},
    ],
    "Mexico": [
        {"name": "Santiago Gimenez", "position": "ST", "club": "Feyenoord", "club_league": "Eredivisie"},
        {"name": "Hirving Lozano", "position": "W", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Edson Alvarez", "position": "DM", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Guillermo Ochoa", "position": "GK", "club": "Salernitana", "club_league": "Serie A"},
    ],
    "Canada": [
        {"name": "Alphonso Davies", "position": "FB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Jonathan David", "position": "ST", "club": "Lille", "club_league": "Ligue 1"},
    ],
    "Morocco": [
        {"name": "Achraf Hakimi", "position": "FB", "club": "PSG", "club_league": "Ligue 1"},
        {"name": "Sofyan Amrabat", "position": "DM", "club": "Fenerbahce", "club_league": "Super Lig"},
    ],
    "Switzerland": [
        {"name": "Granit Xhaka", "position": "CM", "club": "Bayer Leverkusen", "club_league": "Bundesliga"},
        {"name": "Manuel Akanji", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
    ],
    "Turkey": [
        {"name": "Hakan Calhanoglu", "position": "CM", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Arda Guler", "position": "AM", "club": "Real Madrid", "club_league": "La Liga"},
    ],
    "Norway": [
        {"name": "Erling Haaland", "position": "ST", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Martin Odegaard", "position": "AM", "club": "Arsenal", "club_league": "Premier League"},
    ],
    "Austria": [
        {"name": "David Alaba", "position": "CB", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Marcel Sabitzer", "position": "CM", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
    ],
    "Colombia": [
        {"name": "Luis Diaz", "position": "W", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "James Rodriguez", "position": "AM", "club": "Rayo Vallecano", "club_league": "La Liga"},
    ],
    "Ecuador": [
        {"name": "Moises Caicedo", "position": "DM", "club": "Chelsea", "club_league": "Premier League"},
    ],
    "Ivory Coast": [],
    "Senegal": [
        {"name": "Sadio Mane", "position": "W", "club": "Al-Nassr", "club_league": "SPL"},
    ],
    "Ghana": [],
    "Egypt": [
        {"name": "Mohamed Salah", "position": "W", "club": "Liverpool", "club_league": "Premier League"},
    ],
    "Saudi Arabia": [],
    "Iran": [
        {"name": "Mehdi Taremi", "position": "ST", "club": "Inter Milan", "club_league": "Serie A"},
    ],
    "Japan": [
        {"name": "Kaoru Mitoma", "position": "W", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Takefusa Kubo", "position": "W", "club": "Real Sociedad", "club_league": "La Liga"},
    ],
    "South Korea": [
        {"name": "Son Heung-min", "position": "W", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Lee Kang-in", "position": "AM", "club": "PSG", "club_league": "Ligue 1"},
    ],
    "Australia": [],
    "Paraguay": [],
    "Scotland": [
        {"name": "Andy Robertson", "position": "FB", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Scott McTominay", "position": "CM", "club": "Napoli", "club_league": "Serie A"},
    ],
    "Sweden": [],
    "Tunisia": [],
    "New Zealand": [],
    "Czech Republic": [],
    "Bosnia and Herzegovina": [],
    "Qatar": [],
    "Haiti": [],
    "Curacao": [],
    "Cape Verde": [],
    "Iraq": [],
    "Algeria": [],
    "Jordan": [],
    "DR Congo": [],
    "Uzbekistan": [],
    "Panama": [],
}


# ── Big 5 league identifiers for rating matching ─────────────────────────

BIG5_LEAGUES = {
    "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
}

BIG5_LEAGUE_ALIASES: dict[str, str] = {
    "Premier League": "ENG-Premier League",
    "La Liga": "ESP-La Liga",
    "Bundesliga": "GER-Bundesliga",
    "Serie A": "ITA-Serie A",
    "Ligue 1": "FRA-Ligue 1",
}


def get_all_teams() -> list[str]:
    """Return all 48 World Cup team names."""
    teams: list[str] = []
    for group_teams in GROUPS.values():
        teams.extend(group_teams)
    return teams


def get_team_group(team: str) -> str | None:
    """Return the group letter for a team, or None if not found."""
    for group_letter, teams in GROUPS.items():
        if team in teams:
            return group_letter
    return None


def get_squad(team: str) -> list[SquadPlayer]:
    """Return the squad for a team as SquadPlayer objects."""
    raw = SQUADS.get(team, [])
    return [
        SquadPlayer(
            name=p["name"],
            position=p["position"],
            club=p["club"],
            club_league=p["club_league"],
        )
        for p in raw
    ]


def is_big5_league(league_name: str) -> bool:
    """Check if a league name refers to a Big 5 league."""
    return league_name in BIG5_LEAGUES or league_name in BIG5_LEAGUE_ALIASES


def enrich_squad_with_ratings(
    squad: list[SquadPlayer],
    ratings_df,  # pd.DataFrame
) -> list[SquadPlayer]:
    """Enrich squad players with ratings from the optimized ratings data.

    Matches by player name (exact → case-insensitive → last-name substring).
    Sets has_rating, rating, and rating_confidence fields.
    """
    import pandas as pd

    if ratings_df.empty:
        return squad

    # Determine the player name column
    name_col = "player" if "player" in ratings_df.columns else "player_name"
    if name_col not in ratings_df.columns:
        return squad

    # Prefer the latest season (2526) for matching, but allow all seasons
    season_col = "season" if "season" in ratings_df.columns else None

    for player in squad:
        match = pd.DataFrame()

        # Try exact name match first
        exact = ratings_df[ratings_df[name_col] == player.name]
        if not exact.empty:
            match = exact
        else:
            # Try case-insensitive match
            ci = ratings_df[
                ratings_df[name_col].str.lower() == player.name.lower()
            ]
            if not ci.empty:
                match = ci
            else:
                # Try last name match (common for transliterated names)
                last_name = player.name.split()[-1]
                ln = ratings_df[
                    ratings_df[name_col].str.lower().str.contains(
                        last_name.lower(), na=False
                    )
                ]
                if not ln.empty:
                    match = ln

        if not match.empty:
            # Prefer 2526 season if available
            if season_col and "2526" in match[season_col].values:
                row = match[match[season_col] == "2526"].iloc[0]
            else:
                row = match.iloc[0]

            score = row.get("optimized_score")
            if pd.notna(score):
                player.has_rating = True
                player.rating = float(score)
                # Confidence based on league coverage
                league = str(row.get("league", ""))
                if is_big5_league(league):
                    player.rating_confidence = "high"
                else:
                    player.rating_confidence = "medium"

    return squad


def enrich_squads_with_ratings(
    ratings_df,  # pd.DataFrame
) -> dict[str, list[SquadPlayer]]:
    """Enrich all WC squads with ratings from player_ratings_optimized.parquet.

    Returns a dict of team_name -> list[SquadPlayer] with rating data filled in.
    """
    result: dict[str, list[SquadPlayer]] = {}
    for team_name in get_all_teams():
        squad = get_squad(team_name)
        result[team_name] = enrich_squad_with_ratings(squad, ratings_df)
    return result


def compute_team_strengths(
    enriched_squads: dict[str, list[SquadPlayer]] | None = None,
    ratings_df=None,  # pd.DataFrame | None
) -> dict[str, float]:
    """Compute a strength score for each World Cup team.

    Combines:
    1. Average rating of squad players with system ratings (weight: 0.5)
    2. Opta win probability if available (weight: 0.3)
    3. Number of Big5 players as a proxy (weight: 0.2)

    Returns a dict of team -> strength score (0-1).
    """
    if enriched_squads is None:
        if ratings_df is None:
            from scoutfootball.app.data_loader import load_player_ratings
            ratings_df = load_player_ratings()
        enriched_squads = enrich_squads_with_ratings(ratings_df)

    strengths: dict[str, float] = {}

    for team_name, squad in enriched_squads.items():
        rated = [p for p in squad if p.has_rating]

        # Component 1: average rating (normalized to 0-1)
        if rated:
            avg_rating = sum(p.rating for p in rated) / len(rated)
            rating_score = min(max((avg_rating - 30) / 70, 0), 1)
        else:
            rating_score = 0.2

        # Component 2: Opta win probability (already 0-1)
        opta_score = OPTA_WIN_PROBABILITY.get(team_name, 0.01)
        opta_normalized = min(opta_score / 0.16, 1.0)

        # Component 3: Big5 player count (proxy for squad quality)
        big5_count = sum(1 for p in squad if p.club_league in BIG5_LEAGUES)
        big5_score = min(big5_count / 10, 1.0)

        strength = (
            0.5 * rating_score
            + 0.3 * opta_normalized
            + 0.2 * big5_score
        )
        strengths[team_name] = strength

    return strengths


def compute_group_predictions(
    team_strengths: dict[str, float],
) -> list[dict]:
    """Estimate group advancement probabilities for all groups.

    Uses a simple strength-ratio model. Returns a list of group dicts,
    each containing group letter, teams with their advancement probabilities.
    """
    results = []
    for letter, teams in GROUPS.items():
        team_strength_pairs = [
            (t, team_strengths.get(t, 0.2)) for t in teams
        ]
        total = sum(s for _, s in team_strength_pairs)

        group_teams = []
        for team, strength in team_strength_pairs:
            p1 = strength / total if total > 0 else 0.25
            remaining_strength = total - strength
            p2 = (
                (remaining_strength / total)
                * (strength / remaining_strength)
                if remaining_strength > 0
                else 0
            )
            p3 = max(1 - p1 - p2, 0)
            group_teams.append({
                "team": team,
                "strength": round(strength, 3),
                "p1st": round(p1, 3),
                "p2nd": round(p2, 3),
                "p3rd": round(p3, 3),
                "p_advance": round(min(p1 + p2, 1.0), 3),
            })

        group_teams.sort(key=lambda x: x["strength"], reverse=True)
        results.append({
            "group": letter,
            "teams": group_teams,
        })

    return results
