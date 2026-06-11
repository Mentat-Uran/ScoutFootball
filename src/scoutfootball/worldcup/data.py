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
    "Algeria": [
        {"name": "Karim Benzema", "position": "ST", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Riyad Mahrez", "position": "AM", "club": "Man City", "club_league": "Premier League"},
        {"name": "Rayan Cherki", "position": "AM", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Rayan Aït-Nouri", "position": "FB", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Yacine Adli", "position": "AM", "club": "Fiorentina", "club_league": "Serie A"},
        {"name": "Andy Delort", "position": "ST", "club": "Montpellier", "club_league": "Ligue 1"},
        {"name": "Mitchell Weiser", "position": "CM", "club": "Werder Bremen", "club_league": "Bundesliga"},
        {"name": "Alexandre Oukidja", "position": "GK", "club": "Metz", "club_league": "Ligue 1"},
        {"name": "Islam Slimani", "position": "ST", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Nabil Bentaleb", "position": "CM", "club": "Angers", "club_league": "Ligue 1"},
        {"name": "Maghnes Akliouche", "position": "W", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Nabil Fekir", "position": "CM", "club": "Betis", "club_league": "La Liga"},
        {"name": "Romain Faivre", "position": "CM", "club": "Brest,Lyon", "club_league": "Ligue 1"},
        {"name": "Amine Gouiri", "position": "ST", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Ramy Bensebaini", "position": "CB", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Farès Chaïbi", "position": "FB", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Ryad Boudebouz", "position": "W", "club": "Montpellier", "club_league": "Ligue 1"},
        {"name": "Maxime Lopez", "position": "CM", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Ishak Belfodil", "position": "W", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Ibrahim Maza", "position": "CM", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Houssem Aouar", "position": "CM", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Saïd Benrahma", "position": "W", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Farid Boulaya", "position": "W", "club": "Metz", "club_league": "Ligue 1"},
    ],
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
        {"name": "Sergio Agüero", "position": "ST", "club": "Man City", "club_league": "Premier League"},
        {"name": "Enzo Fernández", "position": "CM", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Lautaro Martínez", "position": "ST", "club": "Inter", "club_league": "Serie A"},
        {"name": "Mateo Retegui", "position": "ST", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Alejandro Garnacho", "position": "CM", "club": "Man United", "club_league": "Premier League"},
        {"name": "Marcos Acuña", "position": "FB", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Giovani Lo Celso", "position": "W", "club": "Betis", "club_league": "La Liga"},
        {"name": "Lucas Robertone", "position": "CM", "club": "Almeria", "club_league": "La Liga"},
    ],
    "Australia": [
        {"name": "Adama Traoré", "position": "FB", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Aaron Mooy", "position": "CM", "club": "Huddersfield", "club_league": "Premier League"},
        {"name": "Cristian Volpato", "position": "W", "club": "Sassuolo", "club_league": "Serie A"},
        {"name": "Mathew Leckie", "position": "CM", "club": "Hertha", "club_league": "Bundesliga"},
        {"name": "Alessandro Circati", "position": "CB", "club": "Parma", "club_league": "Serie A"},
        {"name": "Jackson Irvine", "position": "CM", "club": "St Pauli", "club_league": "Bundesliga"},
        {"name": "Ajdin Hrustic", "position": "CM", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Mathew Ryan", "position": "GK", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Connor Metcalfe", "position": "W", "club": "St Pauli", "club_league": "Bundesliga"},
        {"name": "Harry Souttar", "position": "CB", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Denis Genreau", "position": "CM", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Cameron Burgess", "position": "FB", "club": "Ipswich", "club_league": "Premier League"},
        {"name": "Rhys Williams", "position": "CB", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Strahinja Erakovic", "position": "CB", "club": "Zenit St. Petersburg", "club_league": "RFPL"},
        {"name": "Adam Federici", "position": "GK", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "George Timotheou", "position": "CB", "club": "Schalke 04", "club_league": "Bundesliga"},
        {"name": "Caleb Watts", "position": "CM", "club": "Southampton", "club_league": "Premier League"},
        {"name": "Brandon Borrello", "position": "W", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Mile Jedinak", "position": "CM", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Tyrese Francois", "position": "CM", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Antonio Arena", "position": "CM", "club": "Roma", "club_league": "Serie A"},
        {"name": "Awer Mabil", "position": "CM", "club": "Cadiz", "club_league": "La Liga"},
        {"name": "Trent Sainsbury", "position": "CM", "club": "Inter", "club_league": "Serie A"},
    ],
    "Austria": [
        {"name": "David Alaba", "position": "CB", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Marcel Sabitzer", "position": "CM", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
        {"name": "Florian Kainz", "position": "CM", "club": "Koln", "club_league": "Bundesliga"},
        {"name": "Kevin Stöger", "position": "CM", "club": "Bochum", "club_league": "Bundesliga"},
        {"name": "Patrick Wimmer", "position": "AM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Sasa Kalajdzic", "position": "ST", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "Kevin Danso", "position": "CB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Burak Yilmaz", "position": "ST", "club": "Lille", "club_league": "Ligue 1"},
        {"name": "Christopher Trimmel", "position": "FB", "club": "Union Berlin", "club_league": "Bundesliga"},
        {"name": "Sandi Lovrić", "position": "CM", "club": "Udinese", "club_league": "Serie A"},
        {"name": "Christoph Baumgartner", "position": "CM", "club": "RasenBallsport Leipzig", "club_league": "Bundesliga"},
        {"name": "Valentino Lazaro", "position": "CM", "club": "Torino", "club_league": "Serie A"},
        {"name": "Michael Gregoritsch", "position": "ST", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Konrad Laimer", "position": "FB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Christian Fuchs", "position": "CB", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Marko Arnautovic", "position": "W", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Marco Friedl", "position": "CB", "club": "Werder Bremen", "club_league": "Bundesliga"},
        {"name": "Martin Hinteregger", "position": "CB", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Alexander Prass", "position": "FB", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Karim Onisiwo", "position": "W", "club": "Mainz", "club_league": "Bundesliga"},
        {"name": "Markus Suttner", "position": "FB", "club": "Ingolstadt", "club_league": "Bundesliga"},
        {"name": "Christoph Klarer", "position": "CB", "club": "Darmstadt 98", "club_league": "Bundesliga"},
        {"name": "Philipp Lienhart", "position": "CB", "club": "Freiburg", "club_league": "Bundesliga"},
    ],
    "Belgium": [
        {"name": "Kevin De Bruyne", "position": "AM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Romelu Lukaku", "position": "ST", "club": "Napoli", "club_league": "Serie A"},
        {"name": "Thibaut Courtois", "position": "GK", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Youri Tielemans", "position": "CM", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Andreas Pereira", "position": "CM", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Eden Hazard", "position": "ST", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Pascal Struijk", "position": "CB", "club": "Leeds", "club_league": "Premier League"},
        {"name": "Loïs Openda", "position": "ST", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Dries Mertens", "position": "ST", "club": "Napoli", "club_league": "Serie A"},
        {"name": "Leandro Trossard", "position": "ST", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Arne Engels", "position": "FB", "club": "Augsburg", "club_league": "Bundesliga"},
        {"name": "Matz Sels", "position": "GK", "club": "Nott'm Forest", "club_league": "Premier League"},
        {"name": "Yannick Carrasco", "position": "FB", "club": "Ath Madrid", "club_league": "La Liga"},
        {"name": "Alexis Saelemaekers", "position": "CM", "club": "Bologna", "club_league": "Serie A"},
        {"name": "Toby Alderweireld", "position": "CB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Diego Moreira", "position": "FB", "club": "Strasbourg", "club_league": "Ligue 1"},
        {"name": "Charles De Ketelaere", "position": "AM", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Bilal El Khannouss", "position": "CM", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Lucas Stassin", "position": "ST", "club": "St Etienne", "club_league": "Ligue 1"},
        {"name": "Thorgan Hazard", "position": "W", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Maxim De Cuyper", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Divock Origi", "position": "ST", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Axel Witsel", "position": "CM", "club": "Dortmund", "club_league": "Bundesliga"},
    ],
    "Bosnia and Herzegovina": [
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
        {"name": "Andreas Pereira", "position": "CM", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Gabriel Jesus", "position": "ST", "club": "Man City", "club_league": "Premier League"},
        {"name": "Matheus Cunha", "position": "W", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Douglas Luiz", "position": "CM", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Bruno Guimarães", "position": "CM", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Roberto Firmino", "position": "ST", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Diego Costa", "position": "ST", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Lyanco", "position": "CB", "club": "Southampton", "club_league": "Premier League"},
        {"name": "Gustavo Hamer", "position": "CM", "club": "Sheffield United", "club_league": "Premier League"},
        {"name": "Matheus Pereira", "position": "CM", "club": "West Brom", "club_league": "Premier League"},
    ],
    "Canada": [
        {"name": "Alphonso Davies", "position": "FB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Jonathan David", "position": "ST", "club": "Lille", "club_league": "Ligue 1"},
        {"name": "Omar Marmoush", "position": "W", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Jonathan de Guzmán", "position": "CM", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Fikayo Tomori", "position": "CB", "club": "Milan", "club_league": "Serie A"},
        {"name": "Bono", "position": "GK", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Bryan Cristante", "position": "CM", "club": "Roma", "club_league": "Serie A"},
        {"name": "Asmir Begovic", "position": "GK", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Cyle Larin", "position": "ST", "club": "Valladolid", "club_league": "La Liga"},
        {"name": "Scott Arfield", "position": "CM", "club": "Burnley", "club_league": "Premier League"},
        {"name": "Tajon Buchanan", "position": "W", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Derek Cornelius", "position": "CB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Ismaël Koné", "position": "CM", "club": "Sassuolo", "club_league": "Serie A"},
        {"name": "Tani Oluwaseyi", "position": "ST", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Junior Hoilett", "position": "W", "club": "Cardiff", "club_league": "Premier League"},
        {"name": "Moïse Bombito", "position": "CB", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Iké Ugbo", "position": "ST", "club": "Troyes", "club_league": "Ligue 1"},
        {"name": "Theo Bair", "position": "ST", "club": "Auxerre", "club_league": "Ligue 1"},
        {"name": "Laurent Ciman", "position": "CB", "club": "Dijon", "club_league": "Ligue 1"},
        {"name": "Stefan Mitrović", "position": "CB", "club": "Getafe", "club_league": "La Liga"},
        {"name": "Daniel Jebbison", "position": "ST", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Theo Corbeanu", "position": "CM", "club": "Granada", "club_league": "La Liga"},
        {"name": "Jacen Russell-Rowe", "position": "ST", "club": "Toulouse", "club_league": "Ligue 1"},
    ],
    "Cape Verde": [
        {"name": "David Silva", "position": "CM", "club": "Man City", "club_league": "Premier League"},
        {"name": "Nuno Tavares", "position": "FB", "club": "Lazio", "club_league": "Serie A"},
        {"name": "Ricardo Pereira", "position": "FB", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Gelson Martins", "position": "FB", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Nélson Semedo", "position": "CB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Manuel Fernandes", "position": "CM", "club": "Lokomotiv Moscow", "club_league": "RFPL"},
        {"name": "Rúben Vezo", "position": "CB", "club": "Levante,Valencia", "club_league": "La Liga"},
        {"name": "Jordan Larsson", "position": "W", "club": "Spartak Moscow", "club_league": "RFPL"},
        {"name": "Nani", "position": "W", "club": "Valencia", "club_league": "La Liga"},
        {"name": "Bebé", "position": "CM", "club": "Rayo Vallecano", "club_league": "La Liga"},
        {"name": "David Costa", "position": "W", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Zé Luís", "position": "ST", "club": "Spartak Moscow", "club_league": "RFPL"},
        {"name": "Thierry Correia", "position": "CB", "club": "Valencia", "club_league": "La Liga"},
        {"name": "Steven Moreira", "position": "CB", "club": "Lorient,Rennes", "club_league": "Ligue 1"},
        {"name": "Logan Costa", "position": "CB", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Ulisses Garcia", "position": "FB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Samir", "position": "CB", "club": "Udinese", "club_league": "Serie A"},
        {"name": "Nuno da Costa", "position": "W", "club": "Auxerre", "club_league": "Ligue 1"},
        {"name": "Renato Veiga", "position": "CB", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Gelson Fernandes", "position": "CM", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Steven Fortes", "position": "CB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Chiquinho", "position": "CB", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Rúben Semedo", "position": "CB", "club": "Huesca", "club_league": "La Liga"},
    ],
    "Colombia": [
        {"name": "Luis Diaz", "position": "W", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "James Rodriguez", "position": "AM", "club": "Rayo Vallecano", "club_league": "La Liga"},
        {"name": "Duván Zapata", "position": "ST", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Carlos Bacca", "position": "ST", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Jhon Córdoba", "position": "ST", "club": "FC Krasnodar", "club_league": "RFPL"},
        {"name": "Daniel Muñoz", "position": "CB", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Yerson Mosquera", "position": "CB", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Luis Muriel", "position": "W", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Johan Mojica", "position": "CB", "club": "Elche", "club_league": "La Liga"},
        {"name": "Yerry Mina", "position": "CB", "club": "Cagliari", "club_league": "Serie A"},
        {"name": "Juan Cuadrado", "position": "FB", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Deiver Machado", "position": "FB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Mateo Cassierra", "position": "ST", "club": "PFC Sochi", "club_league": "RFPL"},
        {"name": "James Rodríguez", "position": "CM", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Davinson Sánchez", "position": "CB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Jeison Murillo", "position": "CB", "club": "Celta", "club_league": "La Liga"},
        {"name": "Jefferson Lerma", "position": "FB", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "David Ospina", "position": "GK", "club": "Napoli", "club_league": "Serie A"},
        {"name": "Brayan Gil", "position": "ST", "club": "Baltika", "club_league": "RFPL"},
        {"name": "Cristhian Mosquera", "position": "CB", "club": "Valencia", "club_league": "La Liga"},
        {"name": "Bernardo Espinosa", "position": "CB", "club": "Girona", "club_league": "La Liga"},
        {"name": "Devis Vásquez", "position": "GK", "club": "Empoli", "club_league": "Serie A"},
        {"name": "Jhon Lucumí", "position": "CB", "club": "Bologna", "club_league": "Serie A"},
    ],
    "Croatia": [
        {"name": "Luka Modric", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Mateo Kovacic", "position": "CM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Joško Gvardiol", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Ivan Perisic", "position": "W", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Borna Sosa", "position": "FB", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "Luka Modrić", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Ivan Perišić", "position": "W", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Christian Pulisic", "position": "AM", "club": "Milan", "club_league": "Serie A"},
        {"name": "Ivan Rakitic", "position": "CM", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Andrej Kramaric", "position": "W", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Josip Ilicic", "position": "W", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Josip Stanisic", "position": "CB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Adrien Thomasson", "position": "CM", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Igor Matanovic", "position": "ST", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Ante Budimir", "position": "ST", "club": "Osasuna", "club_league": "La Liga"},
        {"name": "Dejan Lovren", "position": "CB", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Josko Gvardiol", "position": "CB", "club": "Man City", "club_league": "Premier League"},
        {"name": "Sime Vrsaljko", "position": "CB", "club": "Ath Madrid", "club_league": "La Liga"},
        {"name": "Ivan Paurevic", "position": "FB", "club": "FC Ufa", "club_league": "RFPL"},
        {"name": "Marcelo Brozović", "position": "CM", "club": "Inter", "club_league": "Serie A"},
        {"name": "Lovro Majer", "position": "CM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Kristijan Bistrovic", "position": "CM", "club": "CSKA Moscow", "club_league": "RFPL"},
        {"name": "Branimir Hrgota", "position": "W", "club": "Greuther Fuerth", "club_league": "Bundesliga"},
    ],
    "Curacao": [
        {"name": "Jurriën Timber", "position": "CB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Patrick van Aanholt", "position": "CB", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Jetro Willems", "position": "CB", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Leroy Fer", "position": "FB", "club": "Swansea", "club_league": "Premier League"},
        {"name": "Tyrell Malacia", "position": "CB", "club": "Man United", "club_league": "Premier League"},
        {"name": "Quilindschy Hartman", "position": "CB", "club": "Burnley", "club_league": "Premier League"},
        {"name": "Lutsharel Geertruida", "position": "CB", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Cuco Martina", "position": "FB", "club": "Everton", "club_league": "Premier League"},
        {"name": "Juninho Bacuna", "position": "FB", "club": "Huddersfield", "club_league": "Premier League"},
        {"name": "Jorrel Hato", "position": "CB", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Tahith Chong", "position": "AM", "club": "Luton", "club_league": "Premier League"},
        {"name": "Riechedly Bazoer", "position": "CM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Jürgen Locadia", "position": "ST", "club": "Bochum", "club_league": "Bundesliga"},
        {"name": "Quinten Timber", "position": "CM", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Leandro Bacuna", "position": "FB", "club": "Cardiff", "club_league": "Premier League"},
        {"name": "Charlison Benschop", "position": "CM", "club": "Hannover", "club_league": "Bundesliga"},
        {"name": "Gregory Van der Wiel", "position": "CB", "club": "Cagliari", "club_league": "Serie A"},
        {"name": "Richairo Zivkovic", "position": "CM", "club": "Sheffield United", "club_league": "Premier League"},
    ],
    "Czech Republic": [
        {"name": "Patrik Schick", "position": "ST", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Vladimír Coufal", "position": "FB", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Jakub Jankto", "position": "FB", "club": "Udinese", "club_league": "Serie A"},
        {"name": "Theodor Gebre Selassie", "position": "FB", "club": "Werder Bremen", "club_league": "Bundesliga"},
        {"name": "Petr Cech", "position": "GK", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Jaroslav Plasil", "position": "CM", "club": "Bordeaux", "club_league": "Ligue 1"},
        {"name": "Jiri Pavlenka", "position": "GK", "club": "Werder Bremen", "club_league": "Bundesliga"},
        {"name": "Pavel Sulc", "position": "W", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Tomas Koubek", "position": "GK", "club": "Augsburg", "club_league": "Bundesliga"},
        {"name": "Matej Vydra", "position": "ST", "club": "Burnley", "club_league": "Premier League"},
        {"name": "Tomáš Souček", "position": "CM", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Ales Mateju", "position": "CB", "club": "Brescia", "club_league": "Serie A"},
        {"name": "David Zima", "position": "CB", "club": "Torino", "club_league": "Serie A"},
        {"name": "Alex Král", "position": "CM", "club": "Espanol", "club_league": "La Liga"},
        {"name": "Antonín Barák", "position": "AM", "club": "Fiorentina", "club_league": "Serie A"},
        {"name": "Jaromir Zmrhal", "position": "CM", "club": "Brescia", "club_league": "Serie A"},
        {"name": "Martin Vitík", "position": "CB", "club": "Bologna", "club_league": "Serie A"},
        {"name": "David Jurásek", "position": "FB", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Lukas Pokorny", "position": "CB", "club": "Montpellier", "club_league": "Ligue 1"},
        {"name": "Matej Kovar", "position": "GK", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Jan Kuchta", "position": "ST", "club": "Lokomotiv Moscow", "club_league": "RFPL"},
        {"name": "Antonín Kinský", "position": "GK", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Stefan Simic", "position": "CB", "club": "Crotone", "club_league": "Serie A"},
    ],
    "DR Congo": [
        {"name": "Romelu Lukaku", "position": "ST", "club": "Inter", "club_league": "Serie A"},
        {"name": "Jean-Philippe Mateta", "position": "ST", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Randal Kolo Muani", "position": "ST", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Yoane Wissa", "position": "ST", "club": "Brentford", "club_league": "Premier League"},
        {"name": "Dilane Bakwa", "position": "W", "club": "Strasbourg", "club_league": "Ligue 1"},
        {"name": "Ezri Konsa", "position": "CB", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Christopher Nkunku", "position": "W", "club": "RasenBallsport Leipzig", "club_league": "Bundesliga"},
        {"name": "Youri Tielemans", "position": "W", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Nordi Mukiele", "position": "CB", "club": "Sunderland", "club_league": "Premier League"},
        {"name": "Aaron Wan-Bissaka", "position": "CB", "club": "Man United", "club_league": "Premier League"},
        {"name": "Axel Tuanzebe", "position": "CB", "club": "Ipswich", "club_league": "Premier League"},
        {"name": "Senny Mayulu", "position": "FB", "club": "Paris SG", "club_league": "Ligue 1"},
        {"name": "Pierre Kalulu", "position": "CB", "club": "Milan", "club_league": "Serie A"},
        {"name": "Ridle Baku", "position": "CM", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Axel Disasi", "position": "CB", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Gaël Kakuta", "position": "W", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Arnaud Kalimuendo", "position": "ST", "club": "Rennes", "club_league": "Ligue 1"},
        {"name": "Benik Afobe", "position": "ST", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Terence Kongolo", "position": "CB", "club": "Huddersfield", "club_league": "Premier League"},
        {"name": "Steve Mandanda", "position": "GK", "club": "Rennes", "club_league": "Ligue 1"},
        {"name": "Jordan Lukaku", "position": "CB", "club": "Lazio", "club_league": "Serie A"},
        {"name": "Albert Sambi Lokonga", "position": "CM", "club": "Luton", "club_league": "Premier League"},
        {"name": "Harrison Manzala", "position": "CM", "club": "Amiens", "club_league": "Ligue 1"},
    ],
    "Ecuador": [
        {"name": "Moises Caicedo", "position": "DM", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Pervis Estupiñán", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Christian Noboa", "position": "CM", "club": "PFC Sochi", "club_league": "RFPL"},
        {"name": "Piero Hincapié", "position": "CB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Felipe Caicedo", "position": "ST", "club": "Lazio", "club_league": "Serie A"},
        {"name": "Jackson Porozo", "position": "CB", "club": "Troyes", "club_league": "Ligue 1"},
        {"name": "Antonio Valencia", "position": "FB", "club": "Man United", "club_league": "Premier League"},
        {"name": "Willian Pacho", "position": "CB", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Moisés Caicedo", "position": "CM", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Cristian Ramírez", "position": "CB", "club": "FC Krasnodar", "club_league": "RFPL"},
        {"name": "Gonzalo Plata", "position": "W", "club": "Valladolid", "club_league": "La Liga"},
        {"name": "Enner Valencia", "position": "W", "club": "Everton,West Ham", "club_league": "Premier League"},
        {"name": "Jhoanner Chávez", "position": "FB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Carlos Gruezo", "position": "CM", "club": "Augsburg", "club_league": "Bundesliga"},
        {"name": "Jefferson Montero", "position": "W", "club": "Swansea", "club_league": "Premier League"},
        {"name": "Jeremy Arévalo", "position": "CM", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "John Yeboah", "position": "W", "club": "Venezia", "club_league": "Serie A"},
        {"name": "Aníbal Chalá", "position": "FB", "club": "Dijon", "club_league": "Ligue 1"},
        {"name": "Kendry Páez", "position": "W", "club": "Strasbourg", "club_league": "Ligue 1"},
        {"name": "Jeremy Sarmiento", "position": "CM", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Nilson Angulo", "position": "CM", "club": "Sunderland", "club_league": "Premier League"},
        {"name": "Stiven Plaza", "position": "CM", "club": "Valladolid", "club_league": "La Liga"},
        {"name": "Bryan Cabezas", "position": "CM", "club": "Atalanta", "club_league": "Serie A"},
    ],
    "Egypt": [
        {"name": "Mohamed Salah", "position": "W", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Omar Marmoush", "position": "W", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Stephan El Shaarawy", "position": "AM", "club": "Roma", "club_league": "Serie A"},
        {"name": "Ahmed Hegazy", "position": "CB", "club": "West Brom", "club_league": "Premier League"},
        {"name": "Mostafa Mohamed", "position": "ST", "club": "Nantes", "club_league": "Ligue 1"},
        {"name": "Ramadan Sobhi", "position": "FB", "club": "Stoke", "club_league": "Premier League"},
        {"name": "Mohamed Elneny", "position": "CM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Mohamed Abdelmonem", "position": "CB", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Haissem Hassan", "position": "W", "club": "Oviedo", "club_league": "La Liga"},
        {"name": "Sam Morsy", "position": "CM", "club": "Ipswich", "club_league": "Premier League"},
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
        {"name": "James Maddison", "position": "W", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Michael Olise", "position": "AM", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Ollie Watkins", "position": "ST", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Solly March", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "James Ward-Prowse", "position": "CM", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Raheem Sterling", "position": "ST", "club": "Man City", "club_league": "Premier League"},
        {"name": "Alfie Doughty", "position": "FB", "club": "Luton", "club_league": "Premier League"},
        {"name": "Jacob Murphy", "position": "W", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Callum Wilson", "position": "ST", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Kieran Trippier", "position": "FB", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Dwight McNeil", "position": "W", "club": "Everton", "club_league": "Premier League"},
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
        {"name": "Michael Olise", "position": "AM", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Karim Benzema", "position": "ST", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Ousmane Dembélé", "position": "ST", "club": "Paris SG", "club_league": "Ligue 1"},
        {"name": "Riyad Mahrez", "position": "AM", "club": "Man City", "club_league": "Premier League"},
        {"name": "Jean-Philippe Mateta", "position": "ST", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Bradley Barcola", "position": "ST", "club": "Paris SG", "club_league": "Ligue 1"},
        {"name": "Anthony Martial", "position": "ST", "club": "Man United", "club_league": "Premier League"},
        {"name": "Randal Kolo Muani", "position": "ST", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Rayan Cherki", "position": "AM", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Alexandre Lacazette", "position": "ST", "club": "Arsenal", "club_league": "Premier League"},
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
        {"name": "Pascal Groß", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Julian Brandt", "position": "AM", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Keven Schlotterbeck", "position": "CB", "club": "Bochum", "club_league": "Bundesliga"},
        {"name": "Borna Sosa", "position": "FB", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "David Raum", "position": "FB", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Jonas Hofmann", "position": "AM", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Amos Pieper", "position": "CB", "club": "Werder Bremen", "club_league": "Bundesliga"},
        {"name": "Philipp Förster", "position": "CM", "club": "Bochum", "club_league": "Bundesliga"},
        {"name": "Maximilian Arnold", "position": "CM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Toni Kroos", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Maximilian Mittelstädt", "position": "FB", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "İlkay Gündoğan", "position": "CM", "club": "Barcelona", "club_league": "La Liga"},
    ],
    "Ghana": [
        {"name": "Nico Williams", "position": "CM", "club": "Ath Bilbao", "club_league": "La Liga"},
        {"name": "Jeremie Frimpong", "position": "FB", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Mohammed Kudus", "position": "W", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Jordan Ayew", "position": "AM", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Jamie Leweling", "position": "FB", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "Memphis Depay", "position": "W", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Callum Hudson-Odoi", "position": "FB", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Alfred Duncan", "position": "CM", "club": "Fiorentina", "club_league": "Serie A"},
        {"name": "Iñaki Williams", "position": "AM", "club": "Ath Bilbao", "club_league": "La Liga"},
        {"name": "Danny Welbeck", "position": "ST", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Jeffrey Schlupp", "position": "CM", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Benjamin Henrichs", "position": "FB", "club": "RasenBallsport Leipzig", "club_league": "Bundesliga"},
        {"name": "Ernest Poku", "position": "FB", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Derrick Köhn", "position": "FB", "club": "Werder Bremen", "club_league": "Bundesliga"},
        {"name": "Antoine Semenyo", "position": "W", "club": "Bournemouth,Manchester City", "club_league": "Premier League"},
        {"name": "Thomas Partey", "position": "CM", "club": "Ath Madrid", "club_league": "La Liga"},
        {"name": "Abdul Mumin", "position": "CB", "club": "Rayo Vallecano", "club_league": "La Liga"},
        {"name": "Alidu Seidu", "position": "CB", "club": "Clermont", "club_league": "Ligue 1"},
        {"name": "Ragnar Ache", "position": "ST", "club": "Koln", "club_league": "Bundesliga"},
        {"name": "Ansgar Knauff", "position": "W", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Samuel Amo-Ameyaw", "position": "FB", "club": "Strasbourg", "club_league": "Ligue 1"},
        {"name": "Osman Bukari", "position": "FB", "club": "Nantes", "club_league": "Ligue 1"},
        {"name": "Eddie Nketiah", "position": "ST", "club": "Arsenal", "club_league": "Premier League"},
    ],
    "Haiti": [
        {"name": "Jean-Ricner Bellegarde", "position": "W", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Allan Saint-Maximin", "position": "FB", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Carlens Arcus", "position": "CB", "club": "Angers", "club_league": "Ligue 1"},
        {"name": "Wilson Isidor", "position": "ST", "club": "Sunderland", "club_league": "Premier League"},
        {"name": "Romain Genevois", "position": "CB", "club": "Caen", "club_league": "Ligue 1"},
        {"name": "William Vainqueur", "position": "CM", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Hannes Delcroix", "position": "CB", "club": "Burnley", "club_league": "Premier League"},
        {"name": "Yoann Etienne", "position": "CB", "club": "Lorient", "club_league": "Ligue 1"},
        {"name": "Lenny Joseph", "position": "CM", "club": "Metz", "club_league": "Ligue 1"},
        {"name": "Jeff Louis", "position": "W", "club": "Caen", "club_league": "Ligue 1"},
        {"name": "Yassin Fortuné", "position": "CM", "club": "Angers", "club_league": "Ligue 1"},
        {"name": "Dany Jean", "position": "CM", "club": "Strasbourg", "club_league": "Ligue 1"},
    ],
    "Iran": [
        {"name": "Mehdi Taremi", "position": "ST", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Sardar Azmoun", "position": "W", "club": "Zenit St. Petersburg", "club_league": "RFPL"},
        {"name": "Milad Mohammadi", "position": "CB", "club": "FK Akhmat", "club_league": "RFPL"},
        {"name": "Saman Ghoddos", "position": "W", "club": "Amiens", "club_league": "Ligue 1"},
        {"name": "Mohammad Mohebi", "position": "W", "club": "FC Rostov", "club_league": "RFPL"},
        {"name": "Alireza Jahanbakhsh", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
    ],
    "Iraq": [
        {"name": "Ali Adnan", "position": "CB", "club": "Udinese", "club_league": "Serie A"},
        {"name": "Ameen Al-Dakhil", "position": "CB", "club": "Burnley", "club_league": "Premier League"},
        {"name": "Safaa Hadi", "position": "CM", "club": "Krylya Sovetov Samara", "club_league": "RFPL"},
        {"name": "Aimar Sher", "position": "CM", "club": "Spezia", "club_league": "Serie A"},
        {"name": "Ali Jasim", "position": "CM", "club": "Como", "club_league": "Serie A"},
    ],
    "Ivory Coast": [
    ],
    "Japan": [
        {"name": "Kaoru Mitoma", "position": "W", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Takefusa Kubo", "position": "W", "club": "Real Sociedad", "club_league": "La Liga"},
        {"name": "Ritsu Doan", "position": "W", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Daichi Kamada", "position": "CM", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Genki Haraguchi", "position": "CM", "club": "Union Berlin", "club_league": "Bundesliga"},
        {"name": "Junya Ito", "position": "W", "club": "Reims", "club_league": "Ligue 1"},
        {"name": "Maya Yoshida", "position": "CB", "club": "Sampdoria", "club_league": "Serie A"},
        {"name": "Hiroki Sakai", "position": "CB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Yukinari Sugawara", "position": "CB", "club": "Werder Bremen", "club_league": "Bundesliga"},
        {"name": "Wataru Endo", "position": "CM", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "Takumi Minamino", "position": "W", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Yuya Osako", "position": "W", "club": "Koln", "club_league": "Bundesliga"},
        {"name": "Hiroki Ito", "position": "CB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Takehiro Tomiyasu", "position": "CB", "club": "Bologna", "club_league": "Serie A"},
        {"name": "Shinji Okazaki", "position": "W", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Yuito Suzuki", "position": "CM", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Takashi Usami", "position": "CM", "club": "Fortuna Duesseldorf", "club_league": "Bundesliga"},
        {"name": "Takuma Asano", "position": "W", "club": "Bochum", "club_league": "Bundesliga"},
        {"name": "Takashi Inui", "position": "CM", "club": "Eibar", "club_league": "La Liga"},
        {"name": "Shinji Kagawa", "position": "CM", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Mio Backhaus", "position": "GK", "club": "Werder Bremen", "club_league": "Bundesliga"},
        {"name": "Zion Suzuki", "position": "GK", "club": "Parma", "club_league": "Serie A"},
        {"name": "Yoshinori Muto", "position": "ST", "club": "Mainz", "club_league": "Bundesliga"},
    ],
    "Jordan": [
    ],
    "Mexico": [
        {"name": "Santiago Gimenez", "position": "ST", "club": "Feyenoord", "club_league": "Eredivisie"},
        {"name": "Hirving Lozano", "position": "W", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Edson Alvarez", "position": "DM", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Guillermo Ochoa", "position": "GK", "club": "Salernitana", "club_league": "Serie A"},
        {"name": "Johan Vásquez", "position": "CB", "club": "Genoa", "club_league": "Serie A"},
        {"name": "Iván Sánchez", "position": "CM", "club": "Valladolid", "club_league": "La Liga"},
        {"name": "Chicharito", "position": "ST", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Pablo Martínez", "position": "CM", "club": "Levante", "club_league": "La Liga"},
        {"name": "Andrés Guardado", "position": "CM", "club": "Betis", "club_league": "La Liga"},
        {"name": "Néstor Araújo", "position": "CB", "club": "Celta", "club_league": "La Liga"},
        {"name": "Jesús Corona", "position": "FB", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Jonathan dos Santos", "position": "CM", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "César Montes", "position": "CB", "club": "Lokomotiv Moscow", "club_league": "RFPL"},
        {"name": "Marco Fabián", "position": "W", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Diego Lainez", "position": "CM", "club": "Betis", "club_league": "La Liga"},
        {"name": "Darío Benedetto", "position": "ST", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Héctor Moreno", "position": "CB", "club": "Real Sociedad", "club_league": "La Liga"},
        {"name": "Edgar González", "position": "FB", "club": "Betis", "club_league": "La Liga"},
        {"name": "Carlos Vela", "position": "W", "club": "Real Sociedad", "club_league": "La Liga"},
        {"name": "Héctor Herrera", "position": "CM", "club": "Ath Madrid", "club_league": "La Liga"},
        {"name": "Diego Reyes", "position": "CB", "club": "Espanol", "club_league": "La Liga"},
        {"name": "Alberto García", "position": "GK", "club": "Rayo Vallecano", "club_league": "La Liga"},
        {"name": "Carlos Castro", "position": "ST", "club": "Sporting Gijon", "club_league": "La Liga"},
    ],
    "Morocco": [
        {"name": "Achraf Hakimi", "position": "FB", "club": "PSG", "club_league": "Ligue 1"},
        {"name": "Sofyan Amrabat", "position": "DM", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Loïs Openda", "position": "ST", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Brahim Díaz", "position": "AM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Karim Bellarabi", "position": "FB", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Bilal El Khannouss", "position": "CM", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Sofiane Diop", "position": "AM", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Aymen Barkok", "position": "FB", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Amine Harit", "position": "FB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Yunis Abdelhamid", "position": "CB", "club": "Reims", "club_league": "Ligue 1"},
        {"name": "Bono", "position": "GK", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Abdel Abqar", "position": "CB", "club": "Alaves", "club_league": "La Liga"},
        {"name": "Ilias Akhomach", "position": "CM", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Youssef En-Nesyri", "position": "ST", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Sofiane Boufal", "position": "CM", "club": "Celta", "club_league": "La Liga"},
        {"name": "Abde Ezzalzouli", "position": "CM", "club": "Betis", "club_league": "La Liga"},
        {"name": "Amine Adli", "position": "AM", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Neil El Aynaoui", "position": "CM", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Hamza Sakhi", "position": "CM", "club": "Auxerre", "club_league": "Ligue 1"},
        {"name": "Eliesse Ben Seghir", "position": "W", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Othman El Kabir", "position": "CM", "club": "Ural", "club_league": "RFPL"},
        {"name": "Omar El Hilali", "position": "CB", "club": "Espanol", "club_league": "La Liga"},
        {"name": "Youssef Maleh", "position": "CM", "club": "Fiorentina", "club_league": "Serie A"},
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
        {"name": "Joël Veltman", "position": "CB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Pascal Struijk", "position": "CB", "club": "Leeds", "club_league": "Premier League"},
        {"name": "Nathan Aké", "position": "CB", "club": "Man City", "club_league": "Premier League"},
        {"name": "Marco Asensio", "position": "W", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Wout Weghorst", "position": "ST", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Jeremie Frimpong", "position": "FB", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Kenny Tete", "position": "FB", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Sheraldo Becker", "position": "ST", "club": "Union Berlin", "club_league": "Bundesliga"},
        {"name": "Gustavo Hamer", "position": "CM", "club": "Sheffield United", "club_league": "Premier League"},
        {"name": "Mark Flekken", "position": "GK", "club": "Brentford", "club_league": "Premier League"},
        {"name": "Dean Huijsen", "position": "CB", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Jurriën Timber", "position": "CB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Donyell Malen", "position": "AM", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Branco van den Boomen", "position": "CM", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Jan Paul van Hecke", "position": "CB", "club": "Brighton", "club_league": "Premier League"},
    ],
    "New Zealand": [
        {"name": "Ben Chilwell", "position": "FB", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Liberato Cacace", "position": "FB", "club": "Empoli", "club_league": "Serie A"},
        {"name": "Chris Wood", "position": "ST", "club": "Nott'm Forest", "club_league": "Premier League"},
        {"name": "Winston Reid", "position": "CB", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Sarpreet Singh", "position": "CM", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Ben Old", "position": "AM", "club": "St Etienne", "club_league": "Ligue 1"},
    ],
    "Norway": [
        {"name": "Erling Haaland", "position": "ST", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Martin Odegaard", "position": "AM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Alexander Sørloth", "position": "ST", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Martin Ødegaard", "position": "CM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Jørgen Strand Larsen", "position": "ST", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Julian Ryerson", "position": "FB", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Aron Dønnum", "position": "FB", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Kristoffer Ajer", "position": "CB", "club": "Brentford", "club_league": "Premier League"},
        {"name": "Filip Jørgensen", "position": "GK", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Antonio Nusa", "position": "FB", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Birger Meling", "position": "CB", "club": "Nimes", "club_league": "Ligue 1"},
        {"name": "Joshua King", "position": "W", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Warren Kamanzi", "position": "CB", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Mathias Normann", "position": "CM", "club": "Norwich", "club_league": "Premier League"},
        {"name": "David Møller Wolfe", "position": "CB", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Rune Jarstein", "position": "GK", "club": "Hertha", "club_league": "Bundesliga"},
        {"name": "Marcus Pedersen", "position": "FB", "club": "Torino", "club_league": "Serie A"},
        {"name": "Elbasan Rashani", "position": "W", "club": "Clermont", "club_league": "Ligue 1"},
        {"name": "Valon Berisha", "position": "CM", "club": "Reims", "club_league": "Ligue 1"},
        {"name": "Morten Thorsby", "position": "CM", "club": "Cremonese,Genoa", "club_league": "Serie A"},
        {"name": "Ørjan Nyland", "position": "GK", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Haitam Aleesami", "position": "FB", "club": "Palermo", "club_league": "Serie A"},
        {"name": "Kristian Thorstvedt", "position": "CM", "club": "Sassuolo", "club_league": "Serie A"},
    ],
    "Panama": [
        {"name": "Amir Murillo", "position": "FB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Andrés Andrade", "position": "CB", "club": "Arminia Bielefeld", "club_league": "Bundesliga"},
    ],
    "Paraguay": [
        {"name": "Miguel Almirón", "position": "ST", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Antonio Sanabria", "position": "ST", "club": "Torino", "club_league": "Serie A"},
        {"name": "Omar Alderete", "position": "CB", "club": "Sunderland", "club_league": "Premier League"},
        {"name": "Lorenzo Melgarejo", "position": "FB", "club": "Spartak Moscow", "club_league": "RFPL"},
        {"name": "Fabián Balbuena", "position": "CB", "club": "Dinamo Moscow", "club_league": "RFPL"},
        {"name": "Julio Enciso", "position": "W", "club": "Strasbourg", "club_league": "Ligue 1"},
        {"name": "Federico Santander", "position": "ST", "club": "Bologna", "club_league": "Serie A"},
        {"name": "Hernán Pérez", "position": "CM", "club": "Espanol", "club_league": "La Liga"},
        {"name": "Diego González", "position": "CB", "club": "Elche", "club_league": "La Liga"},
        {"name": "Darío Lezcano", "position": "ST", "club": "Ingolstadt", "club_league": "Bundesliga"},
        {"name": "Diego Gómez", "position": "W", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Raúl Bobadilla", "position": "W", "club": "Augsburg", "club_league": "Bundesliga"},
        {"name": "Juan Iturbe", "position": "W", "club": "Roma,Torino", "club_league": "Serie A"},
        {"name": "Christian Ordóñez", "position": "CM", "club": "Parma", "club_league": "Serie A"},
        {"name": "Óscar Romero", "position": "CM", "club": "Alaves", "club_league": "La Liga"},
        {"name": "Ramón Sosa", "position": "CM", "club": "Nott'm Forest", "club_league": "Premier League"},
        {"name": "Alexis Duarte", "position": "CB", "club": "Spartak Moscow", "club_league": "RFPL"},
        {"name": "Julio Soler", "position": "CB", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Matías Pérez", "position": "CB", "club": "Lecce", "club_league": "Serie A"},
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
        {"name": "José Sá", "position": "GK", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Pedro Neto", "position": "AM", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Diogo Leite", "position": "CB", "club": "Union Berlin", "club_league": "Bundesliga"},
        {"name": "André Silva", "position": "ST", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Raphaël Guerreiro", "position": "FB", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "David Silva", "position": "CM", "club": "Man City", "club_league": "Premier League"},
        {"name": "Mathias Pereira Lage", "position": "AM", "club": "Brest", "club_league": "Ligue 1"},
        {"name": "Rafael Leão", "position": "AM", "club": "Milan", "club_league": "Serie A"},
        {"name": "Mateus Fernandes", "position": "CM", "club": "Southampton", "club_league": "Premier League"},
        {"name": "Yan Couto", "position": "FB", "club": "Girona", "club_league": "La Liga"},
        {"name": "Francisco Conceição", "position": "CM", "club": "Juventus", "club_league": "Serie A"},
        {"name": "João Cancelo", "position": "CB", "club": "Man City", "club_league": "Premier League"},
        {"name": "Rodri", "position": "FB", "club": "Betis", "club_league": "La Liga"},
    ],
    "Qatar": [
        {"name": "Akram Afif", "position": "CM", "club": "Sporting Gijon", "club_league": "La Liga"},
    ],
    "Saudi Arabia": [
        {"name": "Saud Abdulhamid", "position": "CB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Rhys Norrington-Davies", "position": "CB", "club": "Sheffield United", "club_league": "Premier League"},
    ],
    "Scotland": [
        {"name": "Andy Robertson", "position": "FB", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Scott McTominay", "position": "CM", "club": "Napoli", "club_league": "Serie A"},
        {"name": "Andrew Robertson", "position": "FB", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "John McGinn", "position": "CM", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Harvey Barnes", "position": "W", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Ryan Fraser", "position": "W", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Elliot Anderson", "position": "W", "club": "Nott'm Forest", "club_league": "Premier League"},
        {"name": "Stuart Armstrong", "position": "FB", "club": "Southampton", "club_league": "Premier League"},
        {"name": "Tom Cairney", "position": "CM", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Ryan Christie", "position": "CM", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "James McArthur", "position": "CM", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Matt Ritchie", "position": "FB", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Robert Snodgrass", "position": "W", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Matt Targett", "position": "CB", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Kieran Tierney", "position": "CB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Archie Gray", "position": "FB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "James Morrison", "position": "CM", "club": "West Brom", "club_league": "Premier League"},
        {"name": "Matt Phillips", "position": "W", "club": "West Brom", "club_league": "Premier League"},
        {"name": "Ryan Fredericks", "position": "CB", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Charlie Adam", "position": "CM", "club": "Stoke", "club_league": "Premier League"},
        {"name": "Callum Paterson", "position": "FB", "club": "Cardiff", "club_league": "Premier League"},
        {"name": "Jarell Quansah", "position": "CB", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "John Fleck", "position": "CM", "club": "Sheffield United", "club_league": "Premier League"},
    ],
    "Senegal": [
        {"name": "Sadio Mane", "position": "W", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Youssouf Sabaly", "position": "CB", "club": "Betis", "club_league": "La Liga"},
        {"name": "Nicolas Jackson", "position": "ST", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Lamine Camara", "position": "CM", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Lys Mousset", "position": "ST", "club": "Sheffield United", "club_league": "Premier League"},
        {"name": "Sadio Mané", "position": "W", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Yehvann Diouf", "position": "GK", "club": "Reims", "club_league": "Ligue 1"},
        {"name": "Pape Sarr", "position": "CM", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Oumar Niasse", "position": "ST", "club": "Everton", "club_league": "Premier League"},
        {"name": "Issa Diop", "position": "CB", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Ismail Jakobs", "position": "FB", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Djibril Sow", "position": "CM", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Iliman Ndiaye", "position": "CM", "club": "Everton", "club_league": "Premier League"},
        {"name": "Kalidou Koulibaly", "position": "CB", "club": "Napoli", "club_league": "Serie A"},
        {"name": "Pape Matar Sarr", "position": "CM", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Ferland Mendy", "position": "CB", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Boulaye Dia", "position": "ST", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Noah Fadiga", "position": "CB", "club": "Brest", "club_league": "Ligue 1"},
        {"name": "Mory Diaw", "position": "GK", "club": "Clermont", "club_league": "Ligue 1"},
        {"name": "Habib Diallo", "position": "ST", "club": "Metz", "club_league": "Ligue 1"},
        {"name": "Cheikhou Kouyaté", "position": "FB", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Mamadou Sakho", "position": "CB", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Idrissa Gueye", "position": "CM", "club": "Everton", "club_league": "Premier League"},
    ],
    "South Africa": [
        {"name": "Andrew Surman", "position": "CM", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Lebo Mothiba", "position": "ST", "club": "Lille,Strasbourg", "club_league": "Ligue 1"},
        {"name": "Keagan Dolly", "position": "CM", "club": "Montpellier", "club_league": "Ligue 1"},
        {"name": "Lyle Foster", "position": "W", "club": "Burnley", "club_league": "Premier League"},
        {"name": "Lebogang Phiri", "position": "CM", "club": "Guingamp", "club_league": "Ligue 1"},
        {"name": "Bongani Zungu", "position": "CM", "club": "Amiens", "club_league": "Ligue 1"},
        {"name": "Steven Pienaar", "position": "W", "club": "Sunderland", "club_league": "Premier League"},
        {"name": "Joel Untersee", "position": "CB", "club": "Empoli", "club_league": "Serie A"},
    ],
    "South Korea": [
        {"name": "Son Heung-min", "position": "W", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Lee Kang-in", "position": "AM", "club": "PSG", "club_league": "Ligue 1"},
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
        {"name": "Sergio Agüero", "position": "ST", "club": "Man City", "club_league": "Premier League"},
        {"name": "Lionel Messi", "position": "ST", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Pedro Porro", "position": "FB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Aarón Martín", "position": "FB", "club": "Mainz", "club_league": "Bundesliga"},
        {"name": "Marco Asensio", "position": "W", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Sergio Gómez", "position": "FB", "club": "Real Sociedad", "club_league": "La Liga"},
        {"name": "Sergi Darder", "position": "CM", "club": "Mallorca", "club_league": "La Liga"},
        {"name": "Pablo Sarabia", "position": "AM", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Aleix García", "position": "CM", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Rodrigo Riquelme", "position": "FB", "club": "Ath Madrid", "club_league": "La Liga"},
        {"name": "Luis Alberto", "position": "CM", "club": "Lazio", "club_league": "Serie A"},
    ],
    "Sweden": [
        {"name": "Anthony Elanga", "position": "AM", "club": "Nott'm Forest", "club_league": "Premier League"},
        {"name": "Alexander Isak", "position": "ST", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Mattias Svanberg", "position": "CM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Dejan Kulusevski", "position": "W", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Yasin Ayari", "position": "CM", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Emil Forsberg", "position": "W", "club": "RasenBallsport Leipzig", "club_league": "Bundesliga"},
        {"name": "Williot Swedberg", "position": "W", "club": "Celta", "club_league": "La Liga"},
        {"name": "Riccardo Gagliolo", "position": "CB", "club": "Parma", "club_league": "Serie A"},
        {"name": "Pontus Jansson", "position": "CB", "club": "Brentford", "club_league": "Premier League"},
        {"name": "Lucas Bergvall", "position": "CM", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Karl-Johan Johnsson", "position": "GK", "club": "Guingamp", "club_league": "Ligue 1"},
        {"name": "Viktor Claesson", "position": "W", "club": "FC Krasnodar", "club_league": "RFPL"},
        {"name": "Victor Lindelöf", "position": "CB", "club": "Man United", "club_league": "Premier League"},
        {"name": "Niclas Eliasson", "position": "FB", "club": "Nimes", "club_league": "Ligue 1"},
        {"name": "Branimir Hrgota", "position": "W", "club": "Greuther Fuerth", "club_league": "Bundesliga"},
        {"name": "Jordan Larsson", "position": "W", "club": "Spartak Moscow", "club_league": "RFPL"},
        {"name": "Emil Holm", "position": "CB", "club": "Bologna,Juventus", "club_league": "Serie A"},
        {"name": "Gabriel Gudmundsson", "position": "FB", "club": "Lille", "club_league": "Ligue 1"},
        {"name": "Sebastian Nanasi", "position": "CM", "club": "Strasbourg", "club_league": "Ligue 1"},
        {"name": "Kristoffer Olsson", "position": "CM", "club": "FC Krasnodar", "club_league": "RFPL"},
        {"name": "Miiko Albornoz", "position": "FB", "club": "Hannover", "club_league": "Bundesliga"},
        {"name": "Robin Quaison", "position": "W", "club": "Mainz", "club_league": "Bundesliga"},
        {"name": "Ludwig Augustinsson", "position": "FB", "club": "Werder Bremen", "club_league": "Bundesliga"},
    ],
    "Switzerland": [
        {"name": "Granit Xhaka", "position": "CM", "club": "Bayer Leverkusen", "club_league": "Bundesliga"},
        {"name": "Manuel Akanji", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Fabian Schär", "position": "CB", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Berat Djimsiti", "position": "CB", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Xherdan Shaqiri", "position": "CM", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Ivan Rakitic", "position": "CM", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Renato Steffen", "position": "FB", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Breel Embolo", "position": "W", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Vincent Sierro", "position": "CM", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Djibril Sow", "position": "CM", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Fabian Rieder", "position": "FB", "club": "Augsburg", "club_league": "Bundesliga"},
        {"name": "Yann Sommer", "position": "GK", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Senad Lulic", "position": "FB", "club": "Lazio", "club_league": "Serie A"},
        {"name": "Ezgjan Alioski", "position": "FB", "club": "Leeds", "club_league": "Premier League"},
        {"name": "Steven Zuber", "position": "FB", "club": "Hoffenheim,VfB Stuttgart", "club_league": "Bundesliga"},
        {"name": "Nico Elvedi", "position": "CB", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Admir Mehmedi", "position": "W", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Ricardo Rodríguez", "position": "CB", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Yvon Mvogo", "position": "GK", "club": "Lorient", "club_league": "Ligue 1"},
        {"name": "Johan Manzambi", "position": "CM", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Remo Freuler", "position": "CM", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Dan Ndoye", "position": "AM", "club": "Bologna", "club_league": "Serie A"},
        {"name": "Kevin Mbabu", "position": "FB", "club": "Augsburg", "club_league": "Bundesliga"},
    ],
    "Tunisia": [
        {"name": "Wissam Ben Yedder", "position": "ST", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Saîf-Eddine Khaoui", "position": "CM", "club": "Clermont", "club_league": "Ligue 1"},
        {"name": "Yasin Ayari", "position": "CM", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Ali Abdi", "position": "CM", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Oussama Haddadi", "position": "CB", "club": "Dijon", "club_league": "Ligue 1"},
        {"name": "Wahbi Khazri", "position": "W", "club": "St Etienne", "club_league": "Ligue 1"},
        {"name": "Karim Rekik", "position": "CB", "club": "Hertha", "club_league": "Bundesliga"},
        {"name": "Dylan Bronn", "position": "CB", "club": "Metz", "club_league": "Ligue 1"},
        {"name": "Sami Khedira", "position": "CM", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Ellyes Skhiri", "position": "CM", "club": "Koln", "club_league": "Bundesliga"},
        {"name": "Rani Khedira", "position": "FB", "club": "Augsburg", "club_league": "Bundesliga"},
        {"name": "Montassar Talbi", "position": "CB", "club": "Lorient", "club_league": "Ligue 1"},
        {"name": "Aïssa Laïdouni", "position": "CM", "club": "Union Berlin", "club_league": "Bundesliga"},
        {"name": "Mohamed Dräger", "position": "FB", "club": "Paderborn", "club_league": "Bundesliga"},
        {"name": "Yan Valery", "position": "FB", "club": "Southampton", "club_league": "Premier League"},
        {"name": "Alaeddine Yahia", "position": "CB", "club": "Caen", "club_league": "Ligue 1"},
        {"name": "Elias Saad", "position": "W", "club": "St Pauli", "club_league": "Bundesliga"},
        {"name": "Sami Allagui", "position": "CM", "club": "Hertha", "club_league": "Bundesliga"},
        {"name": "Bassem Srarfi", "position": "W", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Syam Ben Youssef", "position": "CB", "club": "Caen", "club_league": "Ligue 1"},
        {"name": "Nader Ghandri", "position": "CB", "club": "FK Akhmat", "club_league": "RFPL"},
        {"name": "Yohan Benalouane", "position": "CB", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Aymen Abdennour", "position": "CB", "club": "Valencia", "club_league": "La Liga"},
    ],
    "Turkey": [
        {"name": "Hakan Calhanoglu", "position": "CM", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Arda Guler", "position": "AM", "club": "Real Madrid", "club_league": "La Liga"},
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
        {"name": "Nathaniel Brown", "position": "FB", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Julian Ryerson", "position": "FB", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Jonathan David", "position": "ST", "club": "Lille", "club_league": "Ligue 1"},
        {"name": "Brenden Aaronson", "position": "CM", "club": "Leeds", "club_league": "Premier League"},
        {"name": "Pablo Torre", "position": "CM", "club": "Mallorca", "club_league": "La Liga"},
        {"name": "John Brooks", "position": "CB", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Jeremy Toljan", "position": "CB", "club": "Levante", "club_league": "La Liga"},
        {"name": "Kevin Paredes", "position": "FB", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Thomas Delaney", "position": "CM", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "DeAndre Yedlin", "position": "CB", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Joe Scally", "position": "FB", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Timothy Chandler", "position": "FB", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Vedad Ibisevic", "position": "ST", "club": "Hertha", "club_league": "Bundesliga"},
        {"name": "Timothy Weah", "position": "FB", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Tyler Adams", "position": "CM", "club": "Bournemouth", "club_league": "Premier League"},
    ],
    "Uruguay": [
        {"name": "Darwin Nunez", "position": "ST", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Federico Valverde", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Ronald Araujo", "position": "CB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Jose Gimenez", "position": "CB", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Luis Suárez", "position": "ST", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Darwin Núñez", "position": "ST", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Edinson Cavani", "position": "ST", "club": "Paris SG", "club_league": "Ligue 1"},
        {"name": "Emiliano Martínez", "position": "GK", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Rodrigo Zalazar", "position": "AM", "club": "Schalke 04", "club_league": "Bundesliga"},
        {"name": "Nahitan Nández", "position": "FB", "club": "Cagliari", "club_league": "Serie A"},
        {"name": "Leandro Cabrera", "position": "CB", "club": "Espanol", "club_league": "La Liga"},
        {"name": "Santiago Bueno", "position": "CB", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Álvaro Fernández", "position": "CB", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Maxi Gómez", "position": "ST", "club": "Celta", "club_league": "La Liga"},
        {"name": "Gastón Ramírez", "position": "CM", "club": "Sampdoria", "club_league": "Serie A"},
        {"name": "Santiago Mouriño", "position": "CB", "club": "Alaves", "club_league": "La Liga"},
        {"name": "Lucas Olaza", "position": "CB", "club": "Celta Vigo,Real Valladolid", "club_league": "La Liga"},
        {"name": "Diego Godín", "position": "CB", "club": "Ath Madrid", "club_league": "La Liga"},
        {"name": "Martín Cáceres", "position": "CB", "club": "Fiorentina", "club_league": "Serie A"},
        {"name": "Mathías Olivera", "position": "CB", "club": "Getafe", "club_league": "La Liga"},
        {"name": "Mauricio Pereyra", "position": "CM", "club": "FC Krasnodar", "club_league": "RFPL"},
        {"name": "Alfonso Espino", "position": "FB", "club": "Cadiz", "club_league": "La Liga"},
        {"name": "Álvaro González", "position": "CB", "club": "Villarreal", "club_league": "La Liga"},
    ],
    "Uzbekistan": [
        {"name": "Eldor Shomurodov", "position": "ST", "club": "FC Rostov", "club_league": "RFPL"},
        {"name": "Vitaliy Denisov", "position": "CB", "club": "Krylya Sovetov Samara", "club_league": "RFPL"},
        {"name": "Ibrokhimkhalil Yuldoshev", "position": "FB", "club": "Nizhny Novgorod", "club_league": "RFPL"},
        {"name": "Abdukodir Khusanov", "position": "CB", "club": "Lens", "club_league": "Ligue 1"},
    ],
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
