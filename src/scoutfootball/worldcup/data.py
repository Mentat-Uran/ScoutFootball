"""Static data for the 2026 FIFA World Cup (US/Canada/Mexico).

48 teams, 12 groups (A-L), June 11 - July 19 2026.
Group and squad data are built-in; match schedules are generated from the
official fixture pattern.  Squad rosters are expected call-ups based on
recent national team selections and 2025-26 club form — they will be updated
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
NATIONALITY_TO_LEAGUE_COUNTRY: dict[str, list[str]] = {
    "Mexico": ["MEX"], "South Africa": ["RSA"], "South Korea": ["KOR"],
    "Czech Republic": ["CZE"], "Canada": ["CAN"],
    "Bosnia and Herzegovina": ["BIH"], "Qatar": ["QAT"], "Switzerland": ["SUI"],
    "Brazil": ["BRA"], "Morocco": ["MAR"], "Haiti": ["HAI"], "Scotland": ["SCO"],
    "United States": ["USA"], "Paraguay": ["PAR"], "Australia": ["AUS"],
    "Turkey": ["TUR"], "Germany": ["GER"], "Curacao": ["CUW"],
    "Ivory Coast": ["CIV"], "Ecuador": ["ECU"], "Netherlands": ["NED"],
    "Japan": ["JPN"], "Sweden": ["SWE"], "Tunisia": ["TUN"],
    "Belgium": ["BEL"], "Egypt": ["EGY"], "Iran": ["IRN"],
    "New Zealand": ["NZL"], "Spain": ["ESP"], "Cape Verde": ["CPV"],
    "Saudi Arabia": ["KSA"], "Uruguay": ["URU"], "France": ["FRA"],
    "Senegal": ["SEN"], "Iraq": ["IRQ"], "Norway": ["NOR"],
    "Argentina": ["ARG"], "Algeria": ["ALG"], "Austria": ["AUT"],
    "Jordan": ["JOR"], "Portugal": ["POR"], "DR Congo": ["COD"],
    "Uzbekistan": ["UZB"], "Colombia": ["COL"], "England": ["ENG"],
    "Croatia": ["CRO"], "Ghana": ["GHA"], "Panama": ["PAN"],
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

HOSTS = ["United States", "Canada", "Mexico"]
TOURNAMENT_START = "2026-06-11"
TOURNAMENT_END = "2026-07-19"

OPTA_WIN_PROBABILITY: dict[str, float] = {
    "Spain": 0.161, "France": 0.128, "Brazil": 0.112,
    "England": 0.098, "Argentina": 0.087, "Germany": 0.072,
    "Portugal": 0.065, "Netherlands": 0.054, "Uruguay": 0.038,
    "Belgium": 0.032,
}
WIN_PROBABILITY = OPTA_WIN_PROBABILITY


# ── Match schedule ────────────────────────────────────────────────────────

@dataclass
class Match:
    matchday: int
    date: str
    time_et: str
    home: str
    away: str
    venue: str
    city: str
    group: str | None = None
    stage: str = "Group Stage"


def generate_group_stage_matches() -> list[Match]:
    """Generate all 72 group-stage matches (12 groups x 6 matches each).

    Dates span June 11-25 for the group stage.
    Exact times/venues will be updated from FIFA's official fixture list.
    """
    matches: list[Match] = []
    group_start_offsets = {
        "A": 0, "B": 0, "C": 0, "D": 0,
        "E": 1, "F": 1, "G": 1, "H": 1,
        "I": 2, "J": 2, "K": 2, "L": 2,
    }
    matchday_gaps = [0, 6, 12]  # days between matchdays within a group

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
                    matchday=md_idx + 1, date=date_str, time_et=time_et,
                    home=home, away=away, venue=venue, city=city,
                    group=group_letter, stage="Group Stage",
                ))

    return matches


# ── Squad data ────────────────────────────────────────────────────────────

@dataclass
class SquadPlayer:
    name: str
    position: str  # GK/CB/FB/DM/CM/AM/W/ST
    club: str
    club_league: str
    has_rating: bool = False
    rating: float | None = None
    rating_confidence: str = "none"


SQUADS: dict[str, list[dict]] = {
    "Algeria": [
        {"name": "Riyad Mahrez", "position": "W", "club": "Al-Ahli", "club_league": "SPL"},
        {"name": "Rayan Ait-Nouri", "position": "FB", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Ismael Bennacer", "position": "CM", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Ramy Bensebaini", "position": "CB", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Houssem Aouar", "position": "AM", "club": "Al-Ittihad", "club_league": "SPL"},
        {"name": "Amine Gouiri", "position": "ST", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Islam Slimani", "position": "ST", "club": "Mechelen", "club_league": "Jupiler Pro League"},
        {"name": "Hichem Boudaoui", "position": "CM", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Adam Ounas", "position": "W", "club": "Lille", "club_league": "Ligue 1"},
        {"name": "Said Benrahma", "position": "W", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Fares Chaibi", "position": "W", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Nabil Bentaleb", "position": "CM", "club": "Lille", "club_league": "Ligue 1"},
        {"name": "Yacine Adli", "position": "AM", "club": "Fiorentina", "club_league": "Serie A"},
        {"name": "Alexandre Oukidja", "position": "GK", "club": "Metz", "club_league": "Ligue 1"},
        {"name": "Andy Delort", "position": "ST", "club": "Montpellier", "club_league": "Ligue 1"},
        {"name": "Nabil Fekir", "position": "AM", "club": "Betis", "club_league": "La Liga"},
        {"name": "Maghnes Akliouche", "position": "W", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Ryad Boudebouz", "position": "W", "club": "Montpellier", "club_league": "Ligue 1"},
        {"name": "Maxime Lopez", "position": "CM", "club": "Sassuolo", "club_league": "Serie A"},
        {"name": "Ishak Belfodil", "position": "ST", "club": "Brest", "club_league": "Ligue 1"},
        {"name": "Ibrahim Maza", "position": "AM", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Farid Boulaya", "position": "W", "club": "Metz", "club_league": "Ligue 1"},
        {"name": "Djamel Benlamri", "position": "CB", "club": "Qatar SC", "club_league": "Qatar Stars League"},
        {"name": "Aissa Mandi", "position": "CB", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Moustapha Zeghba", "position": "GK", "club": "Almeria", "club_league": "La Liga"},
        {"name": "Mehdi Zeffane", "position": "FB", "club": "Clermont", "club_league": "Ligue 1"},
    ],
    "Argentina": [
        {"name": "Emiliano Martinez", "position": "GK", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Juan Musso", "position": "GK", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Geronimo Rulli", "position": "GK", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Cristian Romero", "position": "CB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Lisandro Martinez", "position": "CB", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Nicolas Otamendi", "position": "CB", "club": "Benfica", "club_league": "Liga Portugal"},
        {"name": "Leonardo Balerdi", "position": "CB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Facundo Medina", "position": "CB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Nicolas Tagliafico", "position": "FB", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Gonzalo Montiel", "position": "FB", "club": "River Plate", "club_league": "Liga Profesional"},
        {"name": "Nahuel Molina", "position": "FB", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Valentin Barco", "position": "FB", "club": "Strasbourg", "club_league": "Ligue 1"},
        {"name": "Leandro Paredes", "position": "DM", "club": "Boca Juniors", "club_league": "Liga Profesional"},
        {"name": "Rodrigo De Paul", "position": "CM", "club": "Inter Miami", "club_league": "MLS"},
        {"name": "Alexis Mac Allister", "position": "CM", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Enzo Fernandez", "position": "CM", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Exequiel Palacios", "position": "CM", "club": "Bayer Leverkusen", "club_league": "Bundesliga"},
        {"name": "Lionel Messi", "position": "AM", "club": "Inter Miami", "club_league": "MLS"},
        {"name": "Giovani Lo Celso", "position": "AM", "club": "Real Betis", "club_league": "La Liga"},
        {"name": "Thiago Almada", "position": "AM", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Nico Paz", "position": "AM", "club": "Como", "club_league": "Serie A"},
        {"name": "Nicolas Gonzalez", "position": "W", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Giuliano Simeone", "position": "W", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Julian Alvarez", "position": "ST", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Lautaro Martinez", "position": "ST", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Jose Manuel Lopez", "position": "ST", "club": "Palmeiras", "club_league": "Brasileirao"},
    ],
    "Australia": [
        {"name": "Mathew Ryan", "position": "GK", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Harry Souttar", "position": "CB", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Jackson Irvine", "position": "CM", "club": "St Pauli", "club_league": "Bundesliga"},
        {"name": "Ajdin Hrustic", "position": "AM", "club": "Salernitana", "club_league": "Serie A"},
        {"name": "Alessandro Circati", "position": "CB", "club": "Parma", "club_league": "Serie A"},
        {"name": "Cameron Burgess", "position": "CB", "club": "Ipswich", "club_league": "Premier League"},
        {"name": "Connor Metcalfe", "position": "CM", "club": "St Pauli", "club_league": "Bundesliga"},
        {"name": "Craig Goodwin", "position": "W", "club": "Al-Wehda", "club_league": "SPL"},
        {"name": "Mitchell Duke", "position": "ST", "club": "Al-Taawoun", "club_league": "SPL"},
        {"name": "Lewis Miller", "position": "FB", "club": "Hibernian", "club_league": "Scottish Premiership"},
        {"name": "Kye Rowles", "position": "CB", "club": "Hearts", "club_league": "Scottish Premiership"},
        {"name": "Riley McGree", "position": "AM", "club": "Middlesbrough", "club_league": "EFL Championship"},
        {"name": "Martin Boyle", "position": "W", "club": "Hibernian", "club_league": "Scottish Premiership"},
        {"name": "Brandon Borrello", "position": "W", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Denis Genreau", "position": "CM", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Awer Mabil", "position": "W", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Joe Gauci", "position": "GK", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Nathaniel Atkinson", "position": "FB", "club": "Hearts", "club_league": "Scottish Premiership"},
        {"name": "Kusini Yengi", "position": "ST", "club": "Portsmouth", "club_league": "EFL Championship"},
        {"name": "Cristian Volpato", "position": "W", "club": "Sassuolo", "club_league": "Serie A"},
        {"name": "Samuel Silvera", "position": "W", "club": "Middlesbrough", "club_league": "EFL Championship"},
        {"name": "Jamie Maclaren", "position": "ST", "club": "Melbourne City", "club_league": "A-League"},
        {"name": "Thomas Deng", "position": "CB", "club": "Yokohama FC", "club_league": "J-League"},
        {"name": "Danny Vukovic", "position": "GK", "club": "Central Coast Mariners", "club_league": "A-League"},
        {"name": "Trent Sainsbury", "position": "CB", "club": "Al-Wakrah", "club_league": "Qatar Stars League"},
        {"name": "Chris Ikonomidis", "position": "W", "club": "Melbourne Victory", "club_league": "A-League"},
    ],
    "Austria": [
        {"name": "David Alaba", "position": "CB", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Marcel Sabitzer", "position": "CM", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
        {"name": "Konrad Laimer", "position": "FB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Christoph Baumgartner", "position": "AM", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Sasa Kalajdzic", "position": "ST", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Kevin Danso", "position": "CB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Patrick Wimmer", "position": "W", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Florian Kainz", "position": "W", "club": "Koln", "club_league": "Bundesliga"},
        {"name": "Marko Arnautovic", "position": "ST", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Michael Gregoritsch", "position": "ST", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Valentino Lazaro", "position": "FB", "club": "Torino", "club_league": "Serie A"},
        {"name": "Marco Friedl", "position": "CB", "club": "Werder Bremen", "club_league": "Bundesliga"},
        {"name": "Philipp Lienhart", "position": "CB", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Stefan Lainer", "position": "FB", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Alexander Prass", "position": "FB", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Sandi Lovric", "position": "CM", "club": "Udinese", "club_league": "Serie A"},
        {"name": "Kevin Stoger", "position": "CM", "club": "Bochum", "club_league": "Bundesliga"},
        {"name": "Maximilian Arnold", "position": "CM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Karim Onisiwo", "position": "W", "club": "Mainz", "club_league": "Bundesliga"},
        {"name": "Heinz Lindner", "position": "GK", "club": "Basel", "club_league": "Swiss Super League"},
        {"name": "Pentz", "position": "GK", "club": "Braga", "club_league": "Liga Portugal"},
        {"name": "Gernot Trauner", "position": "CB", "club": "Feyenoord", "club_league": "Eredivisie"},
        {"name": "Stefan Posch", "position": "CB", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Niklas Hedl", "position": "GK", "club": "Rapid Wien", "club_league": "Austrian Bundesliga"},
        {"name": "Maximilian Wober", "position": "CB", "club": "Leeds", "club_league": "EFL Championship"},
        {"name": "Alessandro Schopf", "position": "W", "club": "Bochum", "club_league": "Bundesliga"},
    ],
    "Belgium": [
        {"name": "Kevin De Bruyne", "position": "AM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Romelu Lukaku", "position": "ST", "club": "Napoli", "club_league": "Serie A"},
        {"name": "Thibaut Courtois", "position": "GK", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Youri Tielemans", "position": "CM", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Leandro Trossard", "position": "W", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Lois Openda", "position": "ST", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Charles De Ketelaere", "position": "AM", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Matz Sels", "position": "GK", "club": "Nott'm Forest", "club_league": "Premier League"},
        {"name": "Bilal El Khannouss", "position": "AM", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Arthur Theate", "position": "CB", "club": "Rennes", "club_league": "Ligue 1"},
        {"name": "Wout Faes", "position": "CB", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Jan Vertonghen", "position": "CB", "club": "Anderlecht", "club_league": "Jupiler Pro League"},
        {"name": "Thomas Meunier", "position": "FB", "club": "Lille", "club_league": "Ligue 1"},
        {"name": "Timothy Castagne", "position": "FB", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Orel Mangala", "position": "CM", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Amadou Onana", "position": "DM", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Maxim De Cuyper", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Dodi Lukebakio", "position": "W", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Johan Bakayoko", "position": "W", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Jeremy Doku", "position": "W", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Zeno Debast", "position": "CB", "club": "Sporting CP", "club_league": "Liga Portugal"},
        {"name": "Aster Vranckx", "position": "CM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Koen Casteels", "position": "GK", "club": "Al-Qadsiah", "club_league": "SPL"},
        {"name": "Thomas Kaminski", "position": "GK", "club": "Luton", "club_league": "EFL Championship"},
        {"name": "Mike Tresor", "position": "AM", "club": "Burnley", "club_league": "EFL Championship"},
        {"name": "Zinho Vanheusden", "position": "CB", "club": "Standard Liege", "club_league": "Jupiler Pro League"},
    ],
    "Bosnia and Herzegovina": [
        {"name": "Edin Dzeko", "position": "ST", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Miralem Pjanic", "position": "CM", "club": "Sharjah", "club_league": "UAE Pro League"},
        {"name": "Sead Kolasinac", "position": "FB", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Anel Ahmedhodzic", "position": "CB", "club": "Sheffield United", "club_league": "EFL Championship"},
        {"name": "Rade Krunic", "position": "CM", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Amar Dedic", "position": "FB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Nikola Vlasic", "position": "AM", "club": "Torino", "club_league": "Serie A"},
        {"name": "Benjamin Tahirovic", "position": "CM", "club": "Ajax", "club_league": "Eredivisie"},
        {"name": "Ermedin Demirovic", "position": "ST", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "Haris Tabakovic", "position": "ST", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Armin Gigovic", "position": "CM", "club": "Rosenborg", "club_league": "Eliteserien"},
        {"name": "Smail Prevljak", "position": "ST", "club": "Basaksehir", "club_league": "Super Lig"},
        {"name": "Jasmin Scuk", "position": "CM", "club": "Basaksehir", "club_league": "Super Lig"},
        {"name": "Nihad Mujakic", "position": "CB", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Adrian Leon Barisic", "position": "CB", "club": "LASK", "club_league": "Austrian Bundesliga"},
        {"name": "Toni Fruk", "position": "W", "club": "Dinamo Zagreb", "club_league": "HNL"},
        {"name": "Kenan Kodro", "position": "ST", "club": "Ferencvaros", "club_league": "NB I"},
        {"name": "Nikola Vasilj", "position": "GK", "club": "St. Pauli", "club_league": "Bundesliga"},
        {"name": "Ibrahim Sehic", "position": "GK", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Asim Lepinja", "position": "GK", "club": "Sarajevo", "club_league": "Premier League BiH"},
        {"name": "Dennis Hadzikadic", "position": "CM", "club": "Alanyaspor", "club_league": "Super Lig"},
        {"name": "Stevan Lukic", "position": "CB", "club": "Tuzla City", "club_league": "Premier League BiH"},
        {"name": "Cristian Martinez", "position": "FB", "club": "Zrinjski", "club_league": "Premier League BiH"},
        {"name": "Gojko Cimirot", "position": "DM", "club": "Al-Fayha", "club_league": "SPL"},
        {"name": "Sanin Prcic", "position": "CM", "club": "Monza", "club_league": "Serie A"},
        {"name": "Jozo Stanic", "position": "CB", "club": "Sturm Graz", "club_league": "Austrian Bundesliga"},
    ],
    "Brazil": [
        {"name": "Alisson", "position": "GK", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Ederson", "position": "GK", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Weverton", "position": "GK", "club": "Gremio", "club_league": "Brasileirao"},
        {"name": "Marquinhos", "position": "CB", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Gabriel", "position": "CB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Bremer", "position": "CB", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Roger Ibanez", "position": "CB", "club": "Al Ahli", "club_league": "SPL"},
        {"name": "Leo Pereira", "position": "CB", "club": "Flamengo", "club_league": "Brasileirao"},
        {"name": "Danilo", "position": "FB", "club": "Flamengo", "club_league": "Brasileirao"},
        {"name": "Alex Sandro", "position": "FB", "club": "Flamengo", "club_league": "Brasileirao"},
        {"name": "Douglas Santos", "position": "FB", "club": "Zenit", "club_league": "RFPL"},
        {"name": "Wesley", "position": "FB", "club": "Roma", "club_league": "Serie A"},
        {"name": "Casemiro", "position": "DM", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Fabinho", "position": "DM", "club": "Al Ittihad", "club_league": "SPL"},
        {"name": "Bruno Guimaraes", "position": "CM", "club": "Newcastle United", "club_league": "Premier League"},
        {"name": "Danilo Santos", "position": "CM", "club": "Botafogo", "club_league": "Brasileirao"},
        {"name": "Paqueta", "position": "AM", "club": "Flamengo", "club_league": "Brasileirao"},
        {"name": "Neymar", "position": "W", "club": "Al Hilal", "club_league": "SPL"},
        {"name": "Vinicius Junior", "position": "W", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Raphinha", "position": "W", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Martinelli", "position": "W", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Luis Henrique", "position": "W", "club": "Zenit", "club_league": "RFPL"},
        {"name": "Rayyan", "position": "W", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Endrick", "position": "ST", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Matheus Cunha", "position": "ST", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Igor Thiago", "position": "ST", "club": "Brentford", "club_league": "Premier League"},
    ],
    "Canada": [
        {"name": "Alphonso Davies", "position": "FB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Jonathan David", "position": "ST", "club": "Lille", "club_league": "Ligue 1"},
        {"name": "Cyle Larin", "position": "ST", "club": "Valladolid", "club_league": "La Liga"},
        {"name": "Tajon Buchanan", "position": "W", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Stephen Eustaquio", "position": "CM", "club": "Porto", "club_league": "Liga Portugal"},
        {"name": "Ismael Kone", "position": "CM", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Derek Cornelius", "position": "CB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Alistair Johnston", "position": "FB", "club": "Celtic", "club_league": "Scottish Premiership"},
        {"name": "Moise Bombito", "position": "CB", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Dayne St. Clair", "position": "GK", "club": "Minnesota United", "club_league": "MLS"},
        {"name": "Maxime Crepeau", "position": "GK", "club": "Portland Timbers", "club_league": "MLS"},
        {"name": "Richie Laryea", "position": "FB", "club": "Toronto FC", "club_league": "MLS"},
        {"name": "Sam Adekugbe", "position": "FB", "club": "Vancouver Whitecaps", "club_league": "MLS"},
        {"name": "Liam Millar", "position": "W", "club": "Preston", "club_league": "EFL Championship"},
        {"name": "Junior Hoilett", "position": "W", "club": "Vancouver Whitecaps", "club_league": "MLS"},
        {"name": "Theo Corbeanu", "position": "W", "club": "Granada", "club_league": "La Liga"},
        {"name": "Jacen Russell-Rowe", "position": "ST", "club": "Columbus Crew", "club_league": "MLS"},
        {"name": "Tani Oluwaseyi", "position": "ST", "club": "Minnesota United", "club_league": "MLS"},
        {"name": "Ike Ugbo", "position": "ST", "club": "Sheffield Wednesday", "club_league": "EFL Championship"},
        {"name": "Mathieu Choiniere", "position": "CM", "club": "CF Montreal", "club_league": "MLS"},
        {"name": "Zachary Brault-Guillard", "position": "FB", "club": "CF Montreal", "club_league": "MLS"},
        {"name": "Kamal Miller", "position": "CB", "club": "Portland Timbers", "club_league": "MLS"},
        {"name": "Jonathan Osorio", "position": "CM", "club": "Toronto FC", "club_league": "MLS"},
        {"name": "Milan Borjan", "position": "GK", "club": "Al-Riyadh", "club_league": "SPL"},
        {"name": "Samuel Piette", "position": "DM", "club": "CF Montreal", "club_league": "MLS"},
        {"name": "Joel Waterman", "position": "CB", "club": "CF Montreal", "club_league": "MLS"},
    ],
    "Cape Verde": [
        {"name": "Nuno Tavares", "position": "FB", "club": "Lazio", "club_league": "Serie A"},
        {"name": "Logan Costa", "position": "CB", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Steven Moreira", "position": "FB", "club": "Columbus Crew", "club_league": "MLS"},
        {"name": "Diney Borges", "position": "CB", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Roberto Lopes", "position": "CB", "club": "Shamrock Rovers", "club_league": "League of Ireland"},
        {"name": "Garry Rodrigues", "position": "W", "club": "Anorthosis", "club_league": "Cypriot First Division"},
        {"name": "Ryan Mendes", "position": "W", "club": "Fatih Karagumruk", "club_league": "Super Lig"},
        {"name": "Jamiro Monteiro", "position": "CM", "club": "Al-Taawoun", "club_league": "SPL"},
        {"name": "Gelson Martins", "position": "W", "club": "Olympiacos", "club_league": "Super League"},
        {"name": "Thierry Correia", "position": "FB", "club": "Valencia", "club_league": "La Liga"},
        {"name": "Kevin Pina", "position": "CM", "club": "Krasnodar", "club_league": "RFPL"},
        {"name": "Vozinha", "position": "GK", "club": "AEL Limassol", "club_league": "Cypriot First Division"},
        {"name": "Marco Soares", "position": "CM", "club": "Omonia", "club_league": "Cypriot First Division"},
        {"name": "Kiki", "position": "CB", "club": "Famalicao", "club_league": "Liga Portugal"},
        {"name": "Willyan Rocha", "position": "CB", "club": "CSKA Moscow", "club_league": "RFPL"},
        {"name": "Djaniny", "position": "ST", "club": "Al-Jazira", "club_league": "UAE Pro League"},
        {"name": "Ze Luis", "position": "ST", "club": "Spartak Moscow", "club_league": "RFPL"},
        {"name": "Patrick Andrade", "position": "CM", "club": "Qarabag", "club_league": "Azerbaijan Premier League"},
        {"name": "Deroy Duarte", "position": "CM", "club": "Spartak Moscow", "club_league": "RFPL"},
        {"name": "Ricardo Duarte", "position": "CB", "club": "Arouca", "club_league": "Liga Portugal"},
        {"name": "Joao Correia", "position": "FB", "club": "Trofense", "club_league": "Liga Portugal"},
        {"name": "Ivan Rodrigues", "position": "GK", "club": "Gil Vicente", "club_league": "Liga Portugal"},
        {"name": "Lisandro Semedo", "position": "W", "club": "Bulgarian team", "club_league": "First Professional League"},
        {"name": "Marcio Rosa", "position": "CB", "club": "Arouca", "club_league": "Liga Portugal"},
        {"name": "Kenny Rocha", "position": "CM", "club": "Nancy", "club_league": "Ligue 2"},
        {"name": "Julio Tavares", "position": "ST", "club": "Dijon", "club_league": "Ligue 2"},
    ],
    "Colombia": [
        {"name": "Luis Diaz", "position": "W", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "James Rodriguez", "position": "AM", "club": "Rayo Vallecano", "club_league": "La Liga"},
        {"name": "Daniel Munoz", "position": "FB", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Davinson Sanchez", "position": "CB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Yerry Mina", "position": "CB", "club": "Cagliari", "club_league": "Serie A"},
        {"name": "Jefferson Lerma", "position": "CM", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Jhon Cordoba", "position": "ST", "club": "Krasnodar", "club_league": "RFPL"},
        {"name": "Juan Cuadrado", "position": "FB", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "David Ospina", "position": "GK", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Johan Mojica", "position": "FB", "club": "Osasuna", "club_league": "La Liga"},
        {"name": "Yerson Mosquera", "position": "CB", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Deiver Machado", "position": "FB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Jhon Lucumi", "position": "CB", "club": "Bologna", "club_league": "Serie A"},
        {"name": "Cristhian Mosquera", "position": "CB", "club": "Valencia", "club_league": "La Liga"},
        {"name": "Luis Muriel", "position": "ST", "club": "Orlando City", "club_league": "MLS"},
        {"name": "Mateus Uribe", "position": "CM", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Gustavo Cuellar", "position": "CM", "club": "Al-Shabab", "club_league": "SPL"},
        {"name": "Richard Rios", "position": "CM", "club": "Palmeiras", "club_league": "Brasileirao"},
        {"name": "Devis Vasquez", "position": "GK", "club": "Empoli", "club_league": "Serie A"},
        {"name": "Santiago Arias", "position": "FB", "club": "Bahia", "club_league": "Brasileirao"},
        {"name": "Miguel Borja", "position": "ST", "club": "River Plate", "club_league": "Liga Profesional"},
        {"name": "Kevin Castano", "position": "CM", "club": "Cruz Azul", "club_league": "Liga MX"},
        {"name": "Jorge Carrascal", "position": "AM", "club": "Dynamo Moscow", "club_league": "RFPL"},
        {"name": "Jhon Duran", "position": "ST", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Yairo Moreno", "position": "FB", "club": "Leon", "club_league": "Liga MX"},
        {"name": "Jader Valencia", "position": "ST", "club": "Millonarios", "club_league": "Liga Profesional"},
    ],
    "Croatia": [
        {"name": "Luka Modric", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Mateo Kovacic", "position": "CM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Josko Gvardiol", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Ivan Perisic", "position": "W", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Borna Sosa", "position": "FB", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "Andrej Kramaric", "position": "ST", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Marcelo Brozovic", "position": "CM", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Lovro Majer", "position": "AM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Josip Stanisic", "position": "FB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Ante Budimir", "position": "ST", "club": "Osasuna", "club_league": "La Liga"},
        {"name": "Igor Matanovic", "position": "ST", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Dominik Livakovic", "position": "GK", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Josip Juranovic", "position": "FB", "club": "Union Berlin", "club_league": "Bundesliga"},
        {"name": "Dejan Lovren", "position": "CB", "club": "PAOK", "club_league": "Super League"},
        {"name": "Mario Pasalic", "position": "AM", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Nikola Vlasic", "position": "AM", "club": "Torino", "club_league": "Serie A"},
        {"name": "Luka Sucic", "position": "AM", "club": "Real Sociedad", "club_league": "La Liga"},
        {"name": "Martin Erlic", "position": "CB", "club": "Sassuolo", "club_league": "Serie A"},
        {"name": "Duje Caleta-Car", "position": "CB", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Nediljko Labrovic", "position": "GK", "club": "Rijeka", "club_league": "HNL"},
        {"name": "Kristijan Jakic", "position": "DM", "club": "Augsburg", "club_league": "Bundesliga"},
        {"name": "Bruno Petkovic", "position": "ST", "club": "Dinamo Zagreb", "club_league": "HNL"},
        {"name": "Borna Barisic", "position": "FB", "club": "Rangers", "club_league": "Scottish Premiership"},
        {"name": "Marko Livaja", "position": "ST", "club": "Hajduk Split", "club_league": "HNL"},
        {"name": "Luka Ivanusec", "position": "W", "club": "Feyenoord", "club_league": "Eredivisie"},
        {"name": "Marin Pongracic", "position": "CB", "club": "Lecce", "club_league": "Serie A"},
    ],
    "Curacao": [
        {"name": "Nathan Ake", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Cuco Martina", "position": "FB", "club": "NAC Breda", "club_league": "Eredivisie"},
        {"name": "Leandro Bacuna", "position": "CM", "club": "Groningen", "club_league": "Eredivisie"},
        {"name": "Juninho Bacuna", "position": "AM", "club": "Groningen", "club_league": "Eredivisie"},
        {"name": "Rangelo Janga", "position": "ST", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Tahith Chong", "position": "W", "club": "Luton", "club_league": "EFL Championship"},
        {"name": "Eloy Room", "position": "GK", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Gino van Kessel", "position": "W", "club": "Slavia Prague", "club_league": "Czech First League"},
        {"name": "Quenten Martinus", "position": "W", "club": "Yokohama FC", "club_league": "J-League"},
        {"name": "Kenji Gorre", "position": "W", "club": "AEL Limassol", "club_league": "Cypriot First Division"},
        {"name": "Jaden Montnor", "position": "ST", "club": "Almere City", "club_league": "Eredivisie"},
        {"name": "Brandon Orilana", "position": "CM", "club": "RKC Waalwijk", "club_league": "Eredivisie"},
        {"name": "Juriën Gaari", "position": "FB", "club": "RKC Waalwijk", "club_league": "Eredivisie"},
        {"name": "Denzel Jubitana", "position": "W", "club": "Charleroi", "club_league": "Jupiler Pro League"},
        {"name": "Gevaro Nepomuceno", "position": "W", "club": "Denizlispor", "club_league": "Super Lig"},
        {"name": "Jearl Margaritha", "position": "W", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Xander Severina", "position": "AM", "club": "Sparta Rotterdam", "club_league": "Eredivisie"},
        {"name": "Joshua Bitter", "position": "CB", "club": "NAC Breda", "club_league": "Eredivisie"},
        {"name": "Micheal Maria", "position": "CB", "club": "Dibba Al-Hisn", "club_league": "UAE Pro League"},
        {"name": "Shanon Bria", "position": "FB", "club": "Eindhoven FC", "club_league": "Eerste Divisie"},
        {"name": "Ayrton Statie", "position": "FB", "club": "Helmond Sport", "club_league": "Eerste Divisie"},
        {"name": "Jarzinho Pieter", "position": "GK", "club": "Caracas", "club_league": "Venezuelan Primera"},
        {"name": "Remko Bicentini", "position": "CB", "club": "RKC Waalwijk", "club_league": "Eredivisie"},
        {"name": "Jerson Cabral", "position": "W", "club": "ADO Den Haag", "club_league": "Eredivisie"},
        {"name": "Charlison Benschop", "position": "ST", "club": "Fortuna Sittard", "club_league": "Eredivisie"},
        {"name": "Tyronne del Pino", "position": "CM", "club": "Sparta Rotterdam", "club_league": "Eredivisie"},
    ],
    "Czech Republic": [
        {"name": "Patrik Schick", "position": "ST", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Vladimir Coufal", "position": "FB", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Tomas Soucek", "position": "CM", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Adam Hlozek", "position": "W", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "David Zima", "position": "CB", "club": "Slavia Prague", "club_league": "Czech First League"},
        {"name": "Ladislav Krejci", "position": "AM", "club": "Sparta Prague", "club_league": "Czech First League"},
        {"name": "Ondrej Kudela", "position": "CB", "club": "Slavia Prague", "club_league": "Czech First League"},
        {"name": "Antonin Barak", "position": "AM", "club": "Fiorentina", "club_league": "Serie A"},
        {"name": "Alex Kral", "position": "CM", "club": "Spartak Moscow", "club_league": "RFPL"},
        {"name": "Jakub Jankto", "position": "W", "club": "Cagliari", "club_league": "Serie A"},
        {"name": "Jan Kuchta", "position": "ST", "club": "Sparta Prague", "club_league": "Czech First League"},
        {"name": "Mojmir Chytil", "position": "ST", "club": "Slavia Prague", "club_league": "Czech First League"},
        {"name": "Vaclav Cerny", "position": "W", "club": "Rangers", "club_league": "Scottish Premiership"},
        {"name": "Martin Durdic", "position": "CB", "club": "Slavia Prague", "club_league": "Czech First League"},
        {"name": "David Jurasek", "position": "FB", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Ondrej Celustka", "position": "CB", "club": "Sparta Prague", "club_league": "Czech First League"},
        {"name": "Lukas Masopust", "position": "W", "club": "Slavia Prague", "club_league": "Czech First League"},
        {"name": "Petr Sevcik", "position": "CM", "club": "Slavia Prague", "club_league": "Czech First League"},
        {"name": "Tomas Kalas", "position": "CB", "club": "Schalke", "club_league": "2. Bundesliga"},
        {"name": "Jindrich Stanek", "position": "GK", "club": "Slavia Prague", "club_league": "Czech First League"},
        {"name": "Ales Mandous", "position": "GK", "club": "Sparta Prague", "club_league": "Czech First League"},
        {"name": "David Pavelka", "position": "CM", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Lukas Provod", "position": "W", "club": "Slavia Prague", "club_league": "Czech First League"},
        {"name": "Tomas Vaclik", "position": "GK", "club": "Olympiacos", "club_league": "Super League"},
        {"name": "Jakub Brabec", "position": "CB", "club": "Aris", "club_league": "Super League"},
        {"name": "Vladimir Darida", "position": "CM", "club": "Aris", "club_league": "Super League"},
    ],
    "DR Congo": [
        {"name": "Cedric Makiadi", "position": "CM", "club": "Al-Fateh", "club_league": "SPL"},
        {"name": "Dieumerci Mbokani", "position": "ST", "club": "Kuwait SC", "club_league": "Kuwait Premier League"},
        {"name": "Yoane Wissa", "position": "W", "club": "Brentford", "club_league": "Premier League"},
        {"name": "Chancel Mbemba", "position": "CB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Arthur Masuaku", "position": "FB", "club": "Besiktas", "club_league": "Super Lig"},
        {"name": "Gaël Kakuta", "position": "AM", "club": "Lance", "club_league": "Ligue 1"},
        {"name": "Samuel Moutoussamy", "position": "CM", "club": "Nantes", "club_league": "Ligue 1"},
        {"name": "Silas Katompa Mvumpa", "position": "W", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "Jackson Muleka", "position": "ST", "club": "Besiktas", "club_league": "Super Lig"},
        {"name": "Oscar Mboza", "position": "CB", "club": "Lugano", "club_league": "Swiss Super League"},
        {"name": "Elikiya Mampuya", "position": "CB", "club": "LASK", "club_league": "Austrian Bundesliga"},
        {"name": "Christian Mawissa", "position": "FB", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Aaron Tshibola", "position": "CM", "club": "Kilmarnock", "club_league": "Scottish Premiership"},
        {"name": "Ricky Tulenge", "position": "GK", "club": "Villarreal B", "club_league": "La Liga"},
        {"name": "Lionel Mpasi", "position": "GK", "club": "Rodez", "club_league": "Ligue 2"},
        {"name": "Patris Mbiakop", "position": "ST", "club": "Hapoel Beer Sheva", "club_league": "Israeli Premier League"},
        {"name": "Glody Ngonda", "position": "FB", "club": "Dijon", "club_league": "Ligue 2"},
        {"name": "Jacques Maghoma", "position": "W", "club": "Al-Ahli Tripoli", "club_league": "Libyan Premier League"},
        {"name": "Firmin Ndombe Mubele", "position": "W", "club": "Astana", "club_league": "Kazakhstan Premier League"},
        {"name": "Marcel Tisserand", "position": "CB", "club": "Al-Ittihad Kalba", "club_league": "UAE Pro League"},
        {"name": "William Balikwisha", "position": "W", "club": "OH Leuven", "club_league": "Jupiler Pro League"},
        {"name": "Meschak Elia", "position": "W", "club": "Young Boys", "club_league": "Swiss Super League"},
        {"name": "Jonathan Bolingi", "position": "ST", "club": "Al-Riffa", "club_league": "Bahrain Premier League"},
        {"name": "Paul-Jose M'Poku", "position": "W", "club": "Al-Fateh", "club_league": "SPL"},
        {"name": "Fabrice N'Sakala", "position": "FB", "club": "Besiktas", "club_league": "Super Lig"},
        {"name": "Jordan Botaka", "position": "W", "club": "Charleroi", "club_league": "Jupiler Pro League"},
    ],
    "Ecuador": [
        {"name": "Moises Caicedo", "position": "CM", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Piero Hincapie", "position": "CB", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Kendry Paez", "position": "AM", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Enner Valencia", "position": "ST", "club": "Inter Miami", "club_league": "MLS"},
        {"name": "William Pacho", "position": "CB", "club": "PSG", "club_league": "Ligue 1"},
        {"name": "Angel Mena", "position": "W", "club": "Leon", "club_league": "Liga MX"},
        {"name": "Gonzalo Plata", "position": "W", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Carlos Gruezo", "position": "DM", "club": "San Jose Earthquakes", "club_league": "MLS"},
        {"name": "Jose Cifuentes", "position": "CM", "club": "Rangers", "club_league": "Scottish Premiership"},
        {"name": "Pervis Estupinan", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Byron Castillo", "position": "FB", "club": "Leon", "club_league": "Liga MX"},
        {"name": "Felix Torres", "position": "CB", "club": "Santos Laguna", "club_league": "Liga MX"},
        {"name": "Jackson Porozo", "position": "CB", "club": "Braga", "club_league": "Liga Portugal"},
        {"name": "Alan Franco", "position": "DM", "club": "Bahia", "club_league": "Brasileirao"},
        {"name": "Jhojan Julio", "position": "CM", "club": "LDU Quito", "club_league": "Ecuadorian Serie A"},
        {"name": "Romario Ibarra", "position": "W", "club": "Pumas", "club_league": "Liga MX"},
        {"name": "Kevin Rodriguez", "position": "ST", "club": "Union SG", "club_league": "Jupiler Pro League"},
        {"name": "Michael Estrada", "position": "ST", "club": "Toluca", "club_league": "Liga MX"},
        {"name": "Alexander Dominguez", "position": "GK", "club": "LDU Quito", "club_league": "Ecuadorian Serie A"},
        {"name": "Galo Realpe", "position": "GK", "club": "Independiente del Valle", "club_league": "Ecuadorian Serie A"},
        {"name": "Joao Ortiz", "position": "CM", "club": "LDU Quito", "club_league": "Ecuadorian Serie A"},
        {"name": "Willian Vargas", "position": "FB", "club": "Sparta Rotterdam", "club_league": "Eredivisie"},
        {"name": "Patrick Sonson", "position": "CB", "club": "Barcelona SC", "club_league": "Ecuadorian Serie A"},
        {"name": "Leonardo Campana", "position": "ST", "club": "Inter Miami", "club_league": "MLS"},
        {"name": "Robert Arboleda", "position": "CB", "club": "Sao Paulo", "club_league": "Brasileirao"},
        {"name": "Xavier Arreaga", "position": "CB", "club": "Seattle Sounders", "club_league": "MLS"},
    ],
    "Egypt": [
        {"name": "Mohamed Salah", "position": "W", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Omar Marmoush", "position": "ST", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Mohamed Elneny", "position": "CM", "club": "Al-Jazira", "club_league": "UAE Pro League"},
        {"name": "Ahmed Hegazi", "position": "CB", "club": "Al-Ittihad", "club_league": "SPL"},
        {"name": "Trezeguet", "position": "W", "club": "Trabzonspor", "club_league": "Super Lig"},
        {"name": "Mostafa Mohamed", "position": "ST", "club": "Nantes", "club_league": "Ligue 1"},
        {"name": "Ahmed Fattouh", "position": "FB", "club": "Zamalek", "club_league": "Egyptian Premier League"},
        {"name": "Omar Gaber", "position": "FB", "club": "Pyramids", "club_league": "Egyptian Premier League"},
        {"name": "Mohamed Abdelmonem", "position": "CB", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Hussein El Shahat", "position": "W", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Amr El Solia", "position": "CM", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Hamdi Fathi", "position": "CM", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Karim Hafez", "position": "CB", "club": "Pyramids", "club_league": "Egyptian Premier League"},
        {"name": "Mahmoud Hassan Trezeguet", "position": "W", "club": "Trabzonspor", "club_league": "Super Lig"},
        {"name": "Zizo", "position": "W", "club": "Zamalek", "club_league": "Egyptian Premier League"},
        {"name": "Emam Ashour", "position": "AM", "club": "Zamalek", "club_league": "Egyptian Premier League"},
        {"name": "Mohamed Sherif", "position": "ST", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Mohamed Abou Gabal", "position": "GK", "club": "Zamalek", "club_league": "Egyptian Premier League"},
        {"name": "Essam El Hadary", "position": "GK", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Ahmed Nabil Kouka", "position": "ST", "club": "Olympiacos", "club_league": "Super League"},
        {"name": "Sam Morsy", "position": "CM", "club": "Ipswich", "club_league": "Premier League"},
        {"name": "Ahmed Sayed", "position": "AM", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Akram Tawfik", "position": "CM", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Ramadan Sobhi", "position": "W", "club": "Pyramids", "club_league": "Egyptian Premier League"},
        {"name": "Mahmoud Wafik", "position": "CM", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Ahmed Yasser", "position": "CB", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
    ],
    "England": [
        {"name": "Jordan Pickford", "position": "GK", "club": "Everton", "club_league": "Premier League"},
        {"name": "Dean Henderson", "position": "GK", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "James Trafford", "position": "GK", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Reece James", "position": "FB", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Tino Livramento", "position": "FB", "club": "Newcastle United", "club_league": "Premier League"},
        {"name": "Djed Spence", "position": "FB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Marc Guehi", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "John Stones", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Ezri Konsa", "position": "CB", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Jarell Quansah", "position": "CB", "club": "Bayer Leverkusen", "club_league": "Bundesliga"},
        {"name": "Dan Burn", "position": "CB", "club": "Newcastle United", "club_league": "Premier League"},
        {"name": "Nico O'Reilly", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Declan Rice", "position": "CM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Jordan Henderson", "position": "CM", "club": "Brentford", "club_league": "Premier League"},
        {"name": "Kobbie Mainoo", "position": "CM", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Elliot Anderson", "position": "CM", "club": "Nottingham Forest", "club_league": "Premier League"},
        {"name": "Jude Bellingham", "position": "AM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Morgan Rogers", "position": "AM", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Eberechi Eze", "position": "AM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Harry Kane", "position": "ST", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Ivan Toney", "position": "ST", "club": "Al Ahli", "club_league": "SPL"},
        {"name": "Ollie Watkins", "position": "ST", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Bukayo Saka", "position": "W", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Marcus Rashford", "position": "W", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Noni Madueke", "position": "W", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Anthony Gordon", "position": "W", "club": "Newcastle United", "club_league": "Premier League"},
    ],
    "France": [
        {"name": "Mike Maignan", "position": "GK", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Brice Samba", "position": "GK", "club": "Rennes", "club_league": "Ligue 1"},
        {"name": "Loris Riese", "position": "GK", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Dayot Upamecano", "position": "CB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "William Saliba", "position": "CB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Ibrahima Konate", "position": "CB", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Lucas Hernandez", "position": "CB", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Maxence Lacroix", "position": "CB", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Jules Kounde", "position": "FB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Digne", "position": "FB", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Malo Gusto", "position": "FB", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Theo Hernandez", "position": "FB", "club": "Al Hilal", "club_league": "SPL"},
        {"name": "Aurelien Tchouameni", "position": "DM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "N'Golo Kante", "position": "DM", "club": "Al Ittihad", "club_league": "SPL"},
        {"name": "Adrien Rabiot", "position": "CM", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Manu Kone", "position": "CM", "club": "Roma", "club_league": "Serie A"},
        {"name": "Warren Zaire-Emery", "position": "CM", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Eduardo Camavinga", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Kylian Mbappe", "position": "ST", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Marcus Thuram", "position": "ST", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Jean-Philippe Mateta", "position": "ST", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Ousmane Dembele", "position": "W", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Michael Olise", "position": "W", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Bradley Barcola", "position": "W", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Desire Doue", "position": "W", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Rayan Cherki", "position": "AM", "club": "Manchester City", "club_league": "Premier League"},
    ],
    "Germany": [
        {"name": "Manuel Neuer", "position": "GK", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Oliver Baumann", "position": "GK", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Alexander Nubel", "position": "GK", "club": "VfB Stuttgart", "club_league": "Bundesliga"},
        {"name": "Antonio Rudiger", "position": "CB", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Nico Schlotterbeck", "position": "CB", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
        {"name": "Jonathan Tah", "position": "CB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Waldemar Anton", "position": "CB", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
        {"name": "Malik Thiaw", "position": "CB", "club": "Newcastle United", "club_league": "Premier League"},
        {"name": "Joshua Kimmich", "position": "FB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "David Raum", "position": "FB", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "Nathaniel Brown", "position": "FB", "club": "Eintracht Frankfurt", "club_league": "Bundesliga"},
        {"name": "Pascal Gross", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Leon Goretzka", "position": "CM", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Aleksandar Pavlovic", "position": "CM", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Nadiem Amiri", "position": "CM", "club": "Mainz 05", "club_league": "Bundesliga"},
        {"name": "Felix Nmecha", "position": "CM", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
        {"name": "Angelo Stiller", "position": "CM", "club": "VfB Stuttgart", "club_league": "Bundesliga"},
        {"name": "Jamal Musiala", "position": "AM", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Florian Wirtz", "position": "AM", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Lennart Karl", "position": "AM", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Jamie Leweling", "position": "W", "club": "VfB Stuttgart", "club_league": "Bundesliga"},
        {"name": "Maximilian Beier", "position": "W", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
        {"name": "Leroy Sane", "position": "W", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Kai Havertz", "position": "ST", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Deniz Undav", "position": "ST", "club": "VfB Stuttgart", "club_league": "Bundesliga"},
        {"name": "Nick Woltemade", "position": "ST", "club": "Newcastle United", "club_league": "Premier League"},
    ],
    "Ghana": [
        {"name": "Mohammed Kudus", "position": "AM", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Thomas Partey", "position": "DM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Jordan Ayew", "position": "W", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Inaki Williams", "position": "ST", "club": "Athletic Bilbao", "club_league": "La Liga"},
        {"name": "Alexander Djiku", "position": "CB", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Tariq Lamptey", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Gideon Mensah", "position": "FB", "club": "Auxerre", "club_league": "Ligue 1"},
        {"name": "Osman Bukari", "position": "W", "club": "Red Star Belgrade", "club_league": "Serbian SuperLiga"},
        {"name": "Ernest Nuamah", "position": "W", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Antoine Semenyo", "position": "W", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Fatawu Issahaku", "position": "W", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Daniel Amartey", "position": "CB", "club": "Besiktas", "club_league": "Super Lig"},
        {"name": "Joseph Aidoo", "position": "CB", "club": "Celta Vigo", "club_league": "La Liga"},
        {"name": "Elisha Owusu", "position": "CM", "club": "Gent", "club_league": "Jupiler Pro League"},
        {"name": "Salis Abdul Samed", "position": "DM", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Abdul Fatawu Hamidu", "position": "FB", "club": "Basaksehir", "club_league": "Super Lig"},
        {"name": "Lawrence Ati-Zigi", "position": "GK", "club": "St. Gallen", "club_league": "Swiss Super League"},
        {"name": "Richard Ofori", "position": "GK", "club": "Orlando Pirates", "club_league": "PSL"},
        {"name": "André Ayew", "position": "ST", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Kamaldeen Sulemana", "position": "W", "club": "Southampton", "club_league": "Premier League"},
        {"name": "Ibrahim Osman", "position": "W", "club": "Feyenoord", "club_league": "Eredivisie"},
        {"name": "Majeed Ashimeru", "position": "CM", "club": "Anderlecht", "club_league": "Jupiler Pro League"},
        {"name": "Mohammed Salisu", "position": "CB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Baba Iddrisu", "position": "DM", "club": "Almeria", "club_league": "La Liga"},
        {"name": "Jonathan Mensah", "position": "CB", "club": "New England Revolution", "club_league": "MLS"},
        {"name": "Denis Odoi", "position": "FB", "club": "Club Brugge", "club_league": "Jupiler Pro League"},
    ],
    "Haiti": [
        {"name": "Duckens Nazon", "position": "ST", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Frantzdy Pierrot", "position": "ST", "club": "Gent", "club_league": "Jupiler Pro League"},
        {"name": "Carlens Arcus", "position": "FB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Bryan Alceus", "position": "CM", "club": "Petrolul Ploiesti", "club_league": "Liga I"},
        {"name": "Wilde-Donald Guerrier", "position": "CM", "club": "Dinamo Batumi", "club_league": "Erovnuli Liga"},
        {"name": "Jean-Kevin Duverne", "position": "CB", "club": "Brest", "club_league": "Ligue 1"},
        {"name": "Ronalde Descollines", "position": "CB", "club": "Cibao FC", "club_league": "Liga Dominicana"},
        {"name": "Mechack Jérôme", "position": "CB", "club": "Charlotte FC", "club_league": "MLS"},
        {"name": "Johnny Placide", "position": "GK", "club": "Caen", "club_league": "Ligue 2"},
        {"name": "Alexis Messidoro", "position": "GK", "club": "Grenoble", "club_league": "Ligue 2"},
        {"name": "Danley Jean Jacques", "position": "CM", "club": "Metz", "club_league": "Ligue 1"},
        {"name": "Exantus Steeven", "position": "W", "club": "AEL Limassol", "club_league": "Cypriot First Division"},
        {"name": "Jeff Louis", "position": "AM", "club": "Tours", "club_league": "National"},
        {"name": "Kevin Lafrance", "position": "CM", "club": "Dunajska Streda", "club_league": "Slovak Super Liga"},
        {"name": "Peterson Joseph", "position": "CM", "club": "Grenoble", "club_league": "Ligue 2"},
        {"name": "Ricardo Ade", "position": "CB", "club": "Inter Turku", "club_league": "Veikkausliiga"},
        {"name": "Bryan Labissiere", "position": "FB", "club": "Racing Santander", "club_league": "La Liga"},
        {"name": "Luis Lindor", "position": "W", "club": "Cibao FC", "club_league": "Liga Dominicana"},
        {"name": "Emmanuel Sanon", "position": "ST", "club": "Santiago Morning", "club_league": "Chilean Primera"},
        {"name": "Melvyn Doremus", "position": "FB", "club": "Annecy", "club_league": "Ligue 2"},
        {"name": "Joseph-Gaetan Herve", "position": "CB", "club": "Bastia", "club_league": "Ligue 2"},
        {"name": "Djimy Alexis", "position": "CB", "club": "Bastia", "club_league": "Ligue 2"},
        {"name": "Johny Placide Jr", "position": "GK", "club": "Cavalry FC", "club_league": "CPL"},
        {"name": "Derrick Etienne", "position": "W", "club": "Atlanta United", "club_league": "MLS"},
        {"name": "Andrew Jean-Baptiste", "position": "CB", "club": "Hapoel Haifa", "club_league": "Israeli Premier League"},
        {"name": "Zachary Herivaux", "position": "CM", "club": "Birmingham", "club_league": "EFL Championship"},
    ],
    "Iran": [
        {"name": "Mehdi Taremi", "position": "ST", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Sardar Azmoun", "position": "ST", "club": "Shabab Al-Ahli", "club_league": "UAE Pro League"},
        {"name": "Alireza Jahanbakhsh", "position": "W", "club": "Feyenoord", "club_league": "Eredivisie"},
        {"name": "Saman Ghoddos", "position": "AM", "club": "Ittihad Kalba", "club_league": "UAE Pro League"},
        {"name": "Ehsan Hajsafi", "position": "FB", "club": "AEK Athens", "club_league": "Super League"},
        {"name": "Ramin Rezaeian", "position": "FB", "club": "Al-Shahania", "club_league": "Qatar Stars League"},
        {"name": "Morteza Pouraliganji", "position": "CB", "club": "Shabab Al-Ahli", "club_league": "UAE Pro League"},
        {"name": "Majid Hosseini", "position": "CB", "club": "Kayserispor", "club_league": "Super Lig"},
        {"name": "Ahmad Nourollahi", "position": "CM", "club": "Al-Wahda", "club_league": "UAE Pro League"},
        {"name": "Karim Ansarifard", "position": "ST", "club": "Aris", "club_league": "Super League"},
        {"name": "Milad Mohammadi", "position": "FB", "club": "Persepolis", "club_league": "Persian Gulf Pro League"},
        {"name": "Omid Ebrahimi", "position": "CM", "club": "Sepahan", "club_league": "Persian Gulf Pro League"},
        {"name": "Ali Gholizadeh", "position": "W", "club": "Konyaspor", "club_league": "Super Lig"},
        {"name": "Vahid Amiri", "position": "W", "club": "Persepolis", "club_league": "Persian Gulf Pro League"},
        {"name": "Hossein Kanaanizadegan", "position": "CB", "club": "Persepolis", "club_league": "Persian Gulf Pro League"},
        {"name": "Alireza Beiranvand", "position": "GK", "club": "Persepolis", "club_league": "Persian Gulf Pro League"},
        {"name": "Amir Abedzadeh", "position": "GK", "club": "Braga", "club_league": "Liga Portugal"},
        {"name": "Saeid Ezatolahi", "position": "CM", "club": "Shabab Al-Ahli", "club_league": "UAE Pro League"},
        {"name": "Shojae Khalilzadeh", "position": "CB", "club": "Al-Rayyan", "club_league": "Qatar Stars League"},
        {"name": "Roozbeh Cheshmi", "position": "CB", "club": "Esteghlal", "club_league": "Persian Gulf Pro League"},
        {"name": "Allahyar Sayyadmanesh", "position": "W", "club": "Istanbul Basaksehir", "club_league": "Super Lig"},
        {"name": "Reza Shekari", "position": "AM", "club": "Tractor", "club_league": "Persian Gulf Pro League"},
        {"name": "Hassan Yazdani", "position": "W", "club": "Sepahan", "club_league": "Persian Gulf Pro League"},
        {"name": "Mehdi Torabi", "position": "AM", "club": "Persepolis", "club_league": "Persian Gulf Pro League"},
        {"name": "Hossein Hosseini", "position": "GK", "club": "Persepolis", "club_league": "Persian Gulf Pro League"},
        {"name": "Aref Aghasi", "position": "CB", "club": "Sepahan", "club_league": "Persian Gulf Pro League"},
    ],
    "Iraq": [
        {"name": "Aymen Hussein", "position": "ST", "club": "Al-Markhiya", "club_league": "Qatar Stars League"},
        {"name": "Mohannad Ali", "position": "ST", "club": "Al-Shorta", "club_league": "Iraqi Premier League"},
        {"name": "Safaa Hadi", "position": "CM", "club": "Al-Shorta", "club_league": "Iraqi Premier League"},
        {"name": "Amjad Attwan", "position": "CM", "club": "Al-Zawraa", "club_league": "Iraqi Premier League"},
        {"name": "Ahmed Yasin", "position": "W", "club": "Duhok", "club_league": "Iraqi Premier League"},
        {"name": "Ali Adnan", "position": "FB", "club": "Al-Zawraa", "club_league": "Iraqi Premier League"},
        {"name": "Rebin Solaka", "position": "CB", "club": "Duhok", "club_league": "Iraqi Premier League"},
        {"name": "Ibrahim Bayesh", "position": "W", "club": "Al-Shorta", "club_league": "Iraqi Premier League"},
        {"name": "Muntadher Mohammed", "position": "CB", "club": "Al-Shorta", "club_league": "Iraqi Premier League"},
        {"name": "Zidane Iqbal", "position": "CM", "club": "Utrecht", "club_league": "Eredivisie"},
        {"name": "Bashar Resan", "position": "CM", "club": "Al-Wakrah", "club_league": "Qatar Stars League"},
        {"name": "Hussein Ali", "position": "W", "club": "Al-Shorta", "club_league": "Iraqi Premier League"},
        {"name": "Alaa Abbas", "position": "ST", "club": "Al-Zawraa", "club_league": "Iraqi Premier League"},
        {"name": "Dhurgham Ismail", "position": "FB", "club": "Al-Shorta", "club_league": "Iraqi Premier League"},
        {"name": "Saad Natiq", "position": "CB", "club": "Al-Zawraa", "club_league": "Iraqi Premier League"},
        {"name": "Mohammed Dawood", "position": "AM", "club": "Duhok", "club_league": "Iraqi Premier League"},
        {"name": "Jalal Hassan", "position": "GK", "club": "Al-Shorta", "club_league": "Iraqi Premier League"},
        {"name": "Mohammed Hameed Farhan", "position": "GK", "club": "Al-Zawraa", "club_league": "Iraqi Premier League"},
        {"name": "Mustafa Saadon", "position": "CB", "club": "Al-Kahraba", "club_league": "Iraqi Premier League"},
        {"name": "Akram Hashim", "position": "GK", "club": "Erbil", "club_league": "Iraqi Premier League"},
        {"name": "Ali Jasim", "position": "W", "club": "Al-Shorta", "club_league": "Iraqi Premier League"},
        {"name": "Muntadher Abdulameer", "position": "CB", "club": "Naft Al-Basra", "club_league": "Iraqi Premier League"},
        {"name": "Ayman Hussein", "position": "ST", "club": "Al-Kahraba", "club_league": "Iraqi Premier League"},
        {"name": "Merthan Akyildiz", "position": "W", "club": "Al-Zawraa", "club_league": "Iraqi Premier League"},
        {"name": "Osama Rashid", "position": "CM", "club": "Al-Quwa Al-Jawiya", "club_league": "Iraqi Premier League"},
        {"name": "Humam Tariq", "position": "AM", "club": "Al-Shorta", "club_league": "Iraqi Premier League"},
    ],
    "Ivory Coast": [
        {"name": "Nicolas Pepe", "position": "W", "club": "Trabzonspor", "club_league": "Super Lig"},
        {"name": "Serge Aurier", "position": "FB", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Franck Kessie", "position": "CM", "club": "Al-Ahli", "club_league": "SPL"},
        {"name": "Wilfried Zaha", "position": "W", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Eric Bailly", "position": "CB", "club": "Besiktas", "club_league": "Super Lig"},
        {"name": "Jean Michael Seri", "position": "CM", "club": "Hull City", "club_league": "EFL Championship"},
        {"name": "Ibrahim Sangare", "position": "CM", "club": "Nottingham Forest", "club_league": "Premier League"},
        {"name": "Simon Deli", "position": "CB", "club": "Adana Demirspor", "club_league": "Super Lig"},
        {"name": "Seko Fofana", "position": "CM", "club": "Al-Ettifaq", "club_league": "SPL"},
        {"name": "Ousmane Diomande", "position": "CB", "club": "Sporting CP", "club_league": "Liga Portugal"},
        {"name": "Jeremie Boga", "position": "W", "club": "Nice", "club_league": "Ligue 1"},
        {"name": "Christian Kouame", "position": "W", "club": "Fiorentina", "club_league": "Serie A"},
        {"name": "Sebastien Haller", "position": "ST", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Jonathan Bamba", "position": "W", "club": "Celta Vigo", "club_league": "La Liga"},
        {"name": "Maxwel Cornet", "position": "W", "club": "Genoa", "club_league": "Serie A"},
        {"name": "Odilon Kossounou", "position": "CB", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Evan Ndicka", "position": "CB", "club": "Roma", "club_league": "Serie A"},
        {"name": "Serge Gnonto", "position": "W", "club": "Ivory Coast NT", "club_league": "Other"},
        {"name": "Yahia Fofana", "position": "GK", "club": "Angers", "club_league": "Ligue 1"},
        {"name": "Badra Ali Sangare", "position": "GK", "club": "JDT", "club_league": "Malaysian Super League"},
        {"name": "Karl Toko Ekambi", "position": "W", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Lazare Amani", "position": "AM", "club": "Union SG", "club_league": "Jupiler Pro League"},
        {"name": "Ghislain Konan", "position": "FB", "club": "Al-Fayha", "club_league": "SPL"},
        {"name": "Wilfried Singo", "position": "FB", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Moussa Niakhate", "position": "CB", "club": "Lyon", "club_league": "Ligue 1"},
        {"name": "Hamed Traore", "position": "AM", "club": "Bournemouth", "club_league": "Premier League"},
    ],
    "Japan": [
        {"name": "Kaoru Mitoma", "position": "W", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Takefusa Kubo", "position": "W", "club": "Real Sociedad", "club_league": "La Liga"},
        {"name": "Wataru Endo", "position": "DM", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Ritsu Doan", "position": "W", "club": "Freiburg", "club_league": "Bundesliga"},
        {"name": "Junya Ito", "position": "W", "club": "Reims", "club_league": "Ligue 1"},
        {"name": "Ayase Ueda", "position": "ST", "club": "Feyenoord", "club_league": "Eredivisie"},
        {"name": "Daizen Maeda", "position": "W", "club": "Celtic", "club_league": "Scottish Premiership"},
        {"name": "Ko Itakura", "position": "CB", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Hiroki Ito", "position": "CB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Yukinari Sugawara", "position": "FB", "club": "Southampton", "club_league": "Premier League"},
        {"name": "Seiya Maikuma", "position": "FB", "club": "Celtic", "club_league": "Scottish Premiership"},
        {"name": "Hidemasa Morita", "position": "CM", "club": "Sporting CP", "club_league": "Liga Portugal"},
        {"name": "Ao Tanaka", "position": "CM", "club": "Leeds", "club_league": "EFL Championship"},
        {"name": "Reo Hatate", "position": "CM", "club": "Celtic", "club_league": "Scottish Premiership"},
        {"name": "Takumi Minamino", "position": "AM", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Keito Nakamura", "position": "W", "club": "Reims", "club_league": "Ligue 1"},
        {"name": "Maya Yoshida", "position": "CB", "club": "LA Galaxy", "club_league": "MLS"},
        {"name": "Zion Suzuki", "position": "GK", "club": "Parma", "club_league": "Serie A"},
        {"name": "Daniel Schmidt", "position": "GK", "club": "Gent", "club_league": "Jupiler Pro League"},
        {"name": "Machida Koki", "position": "CB", "club": "Union SG", "club_league": "Jupiler Pro League"},
        {"name": "Sota Kawasaki", "position": "CM", "club": "Celtic", "club_league": "Scottish Premiership"},
        {"name": "Yuki Otsu", "position": "AM", "club": "Kashiwa Reysol", "club_league": "J-League"},
        {"name": "Koki Ogawa", "position": "ST", "club": "NEC Nijmegen", "club_league": "Eredivisie"},
        {"name": "Hiroki Sakai", "position": "FB", "club": "Urawa Reds", "club_league": "J-League"},
        {"name": "Shuto Machino", "position": "ST", "club": "Holstein Kiel", "club_league": "Bundesliga"},
        {"name": "Ayumu Seko", "position": "CB", "club": "Grasshoppers", "club_league": "Swiss Super League"},
    ],
    "Jordan": [
        {"name": "Mousa Al-Tamari", "position": "W", "club": "Montpellier", "club_league": "Ligue 1"},
        {"name": "Yazan Al-Naimat", "position": "ST", "club": "Al-Arabi", "club_league": "Qatar Stars League"},
        {"name": "Noor Al-Rawabdeh", "position": "CM", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Ibrahim Al-Dawsa", "position": "CM", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Yazan Al-Arab", "position": "CB", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Anas Bani Yaseen", "position": "CB", "club": "Al-Jazeera", "club_league": "Jordanian Pro League"},
        {"name": "Ali Olwan", "position": "W", "club": "Al-Ahli", "club_league": "SPL"},
        {"name": "Hamza Al-Dardour", "position": "ST", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Saeed Murjan", "position": "CM", "club": "Al-Wehdat", "club_league": "Jordanian Pro League"},
        {"name": "Mohammad Abu Hashish", "position": "FB", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Ahmad Al-Ersan", "position": "CB", "club": "Al-Wehdat", "club_league": "Jordanian Pro League"},
        {"name": "Nizar Al-Rashdan", "position": "AM", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Mahmoud Al-Mardi", "position": "W", "club": "Al-Wehdat", "club_league": "Jordanian Pro League"},
        {"name": "Abdallah Nasib", "position": "CB", "club": "Al-Wehdat", "club_league": "Jordanian Pro League"},
        {"name": "Yazeen Al-Bakhit", "position": "W", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Ihsan Haddad", "position": "FB", "club": "Al-Wehdat", "club_league": "Jordanian Pro League"},
        {"name": "Amir Shafi", "position": "GK", "club": "Al-Wehdat", "club_league": "Jordanian Pro League"},
        {"name": "Yazan Abu Arab", "position": "GK", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Mohammad Al-Dmeiri", "position": "FB", "club": "Al-Jazeera", "club_league": "Jordanian Pro League"},
        {"name": "Oday Al-Zuhairy", "position": "CM", "club": "Al-Wehdat", "club_league": "Jordanian Pro League"},
        {"name": "Rashed Al-Tal", "position": "W", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Laith Al-Hyasat", "position": "ST", "club": "Al-Wehdat", "club_league": "Jordanian Pro League"},
        {"name": "Fawzi Al-Rshoud", "position": "DM", "club": "Al-Jazeera", "club_league": "Jordanian Pro League"},
        {"name": "Ahmad Al-Issawi", "position": "GK", "club": "Al-Faisaly", "club_league": "Jordanian Pro League"},
        {"name": "Baha Faisal", "position": "ST", "club": "Al-Jazeera", "club_league": "Jordanian Pro League"},
        {"name": "Anas Al-Awadat", "position": "CM", "club": "Al-Wehdat", "club_league": "Jordanian Pro League"},
    ],
    "Mexico": [
        {"name": "Santiago Gimenez", "position": "ST", "club": "Feyenoord", "club_league": "Eredivisie"},
        {"name": "Hirving Lozano", "position": "W", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Edson Alvarez", "position": "DM", "club": "West Ham", "club_league": "Premier League"},
        {"name": "Raul Jimenez", "position": "ST", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Jesus Gallardo", "position": "FB", "club": "Monterrey", "club_league": "Liga MX"},
        {"name": "Jorge Sanchez", "position": "FB", "club": "Porto", "club_league": "Liga Portugal"},
        {"name": "Cesar Montes", "position": "CB", "club": "Lokomotiv Moscow", "club_league": "RFPL"},
        {"name": "Julio Gonzalez", "position": "GK", "club": "Toluca", "club_league": "Liga MX"},
        {"name": "Guillermo Ochoa", "position": "GK", "club": "Salernitana", "club_league": "Serie A"},
        {"name": "Luis Romo", "position": "CM", "club": "Monterrey", "club_league": "Liga MX"},
        {"name": "Orbelin Pineda", "position": "AM", "club": "AEK Athens", "club_league": "Super League"},
        {"name": "Alexis Vega", "position": "W", "club": "Toluca", "club_league": "Liga MX"},
        {"name": "Uriel Antuna", "position": "W", "club": "Cruz Azul", "club_league": "Liga MX"},
        {"name": "Diego Lainez", "position": "W", "club": "Tigres", "club_league": "Liga MX"},
        {"name": "Erick Gutierrez", "position": "CM", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Henry Martin", "position": "ST", "club": "Club America", "club_league": "Liga MX"},
        {"name": "Johan Vasquez", "position": "CB", "club": "Genoa", "club_league": "Serie A"},
        {"name": "Gerardo Arteaga", "position": "FB", "club": "Genk", "club_league": "Jupiler Pro League"},
        {"name": "Roberto Alvarado", "position": "W", "club": "Cruz Azul", "club_league": "Liga MX"},
        {"name": "Carlos Rodriguez", "position": "CM", "club": "Cruz Azul", "club_league": "Liga MX"},
        {"name": "Jesus Angulo", "position": "FB", "club": "Tigres", "club_league": "Liga MX"},
        {"name": "Omar Campos", "position": "FB", "club": "Club America", "club_league": "Liga MX"},
        {"name": "Rogelio Funes Mori", "position": "ST", "club": "Monterrey", "club_league": "Liga MX"},
        {"name": "Luis Chavez", "position": "CM", "club": "Pachuca", "club_league": "Liga MX"},
        {"name": "Raul Martinez", "position": "GK", "club": "Toluca", "club_league": "Liga MX"},
        {"name": "Gerardo Martin", "position": "CB", "club": "Santos Laguna", "club_league": "Liga MX"},
    ],
    "Morocco": [
        {"name": "Achraf Hakimi", "position": "FB", "club": "PSG", "club_league": "Ligue 1"},
        {"name": "Sofyan Amrabat", "position": "CM", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Nayef Aguerd", "position": "CB", "club": "Real Sociedad", "club_league": "La Liga"},
        {"name": "Hakim Ziyech", "position": "W", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Youssef En-Nesyri", "position": "ST", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Romain Saiss", "position": "CB", "club": "Al-Shabab", "club_league": "SPL"},
        {"name": "Noussair Mazraoui", "position": "FB", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Azzedine Ounahi", "position": "CM", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Selim Amallah", "position": "AM", "club": "Valladolid", "club_league": "La Liga"},
        {"name": "Bilal El Khannouss", "position": "AM", "club": "Leicester", "club_league": "Premier League"},
        {"name": "Yahia Attiyat Allah", "position": "FB", "club": "Wydad", "club_league": "Botola Pro"},
        {"name": "Bounou", "position": "GK", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Munir El Kajoui", "position": "GK", "club": "Al-Tai", "club_league": "SPL"},
        {"name": "Amine Harit", "position": "AM", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Ez Abde", "position": "W", "club": "Betis", "club_league": "La Liga"},
        {"name": "Ismaila Sarr", "position": "W", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Walid Regragui", "position": "FB", "club": "Wydad", "club_league": "Botola Pro"},
        {"name": "Jawad El Yamiq", "position": "CB", "club": "Al-Wehda", "club_league": "SPL"},
        {"name": "Achraf Dari", "position": "CB", "club": "Al-Rayyan", "club_league": "Qatar Stars League"},
        {"name": "Zouhair El-Moutaraji", "position": "W", "club": "Wydad", "club_league": "Botola Pro"},
        {"name": "Soufiane Rahimi", "position": "W", "club": "Al-Ain", "club_league": "UAE Pro League"},
        {"name": "Oussama Idrissi", "position": "W", "club": "Cadiz", "club_league": "La Liga"},
        {"name": "Yahya Jabrane", "position": "CM", "club": "Wydad", "club_league": "Botola Pro"},
        {"name": "Adam Masina", "position": "FB", "club": "Udinese", "club_league": "Serie A"},
        {"name": "Samy Mmaee", "position": "CB", "club": "Ferencvaros", "club_league": "NB I"},
        {"name": "Aymen Barkok", "position": "AM", "club": "Mainz", "club_league": "Bundesliga"},
    ],
    "Netherlands": [
        {"name": "Mark Flekken", "position": "GK", "club": "Bayer Leverkusen", "club_league": "Bundesliga"},
        {"name": "Bart Verbruggen", "position": "GK", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Robin Roefs", "position": "GK", "club": "Sunderland", "club_league": "Premier League"},
        {"name": "Virgil van Dijk", "position": "CB", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Nathan Ake", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Jorrel Hato", "position": "CB", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Jan-Paul van Hecke", "position": "CB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Micky van de Ven", "position": "CB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Denzel Dumfries", "position": "FB", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Jurrien Timber", "position": "FB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Mats Wieffer", "position": "DM", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Marten de Roon", "position": "DM", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Ryan Gravenberch", "position": "CM", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Frenkie de Jong", "position": "CM", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Teun Koopmeiners", "position": "CM", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Tijjani Reijnders", "position": "CM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Quinten Timber", "position": "CM", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Guus Til", "position": "AM", "club": "PSV Eindhoven", "club_league": "Eredivisie"},
        {"name": "Cody Gakpo", "position": "W", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Justin Kluivert", "position": "W", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Noa Lang", "position": "W", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Donyell Malen", "position": "W", "club": "Roma", "club_league": "Serie A"},
        {"name": "Crysencio Summerville", "position": "W", "club": "West Ham United", "club_league": "Premier League"},
        {"name": "Brian Brobbey", "position": "ST", "club": "Sunderland", "club_league": "Premier League"},
        {"name": "Memphis Depay", "position": "ST", "club": "Corinthians", "club_league": "Brasileirao"},
        {"name": "Wout Weghorst", "position": "ST", "club": "Ajax", "club_league": "Eredivisie"},
    ],
    "New Zealand": [
        {"name": "Chris Wood", "position": "ST", "club": "Nottingham Forest", "club_league": "Premier League"},
        {"name": "Winston Reid", "position": "CB", "club": "Wellington Phoenix", "club_league": "A-League"},
        {"name": "Ryan Thomas", "position": "CM", "club": "PEC Zwolle", "club_league": "Eredivisie"},
        {"name": "Marco Rojas", "position": "W", "club": "Melbourne Victory", "club_league": "A-League"},
        {"name": "Kosta Barbarouses", "position": "W", "club": "Wellington Phoenix", "club_league": "A-League"},
        {"name": "Liberato Cacace", "position": "FB", "club": "Empoli", "club_league": "Serie A"},
        {"name": "Joe Bell", "position": "CM", "club": "Viking", "club_league": "Eliteserien"},
        {"name": "Tyler Boyd", "position": "W", "club": "Nashville SC", "club_league": "MLS"},
        {"name": "Michael Boxall", "position": "CB", "club": "Minnesota United", "club_league": "MLS"},
        {"name": "Bill Tuiloma", "position": "CB", "club": "Charleston Battery", "club_league": "USL"},
        {"name": "Sarpreet Singh", "position": "AM", "club": "Hansa Rostock", "club_league": "2. Bundesliga"},
        {"name": "Elijah Just", "position": "AM", "club": "Helsingborg", "club_league": "Allsvenskan"},
        {"name": "Matthew Garbett", "position": "CM", "club": "Frosinone", "club_league": "Serie B"},
        {"name": "Ben Waine", "position": "ST", "club": "Plymouth", "club_league": "EFL Championship"},
        {"name": "Alex Greive", "position": "W", "club": "St. Mirren", "club_league": "Scottish Premiership"},
        {"name": "Oliver Sail", "position": "GK", "club": "Wellington Phoenix", "club_league": "A-League"},
        {"name": "Stefan Marinovic", "position": "GK", "club": "Hapoel Haifa", "club_league": "Israeli Premier League"},
        {"name": "Callan Elliot", "position": "FB", "club": "Wellington Phoenix", "club_league": "A-League"},
        {"name": "Nando Pijnaker", "position": "CB", "club": "Sligo Rovers", "club_league": "League of Ireland"},
        {"name": "Clayton Lewis", "position": "CM", "club": "Wellington Phoenix", "club_league": "A-League"},
        {"name": "Tim Payne", "position": "FB", "club": "Wellington Phoenix", "club_league": "A-League"},
        {"name": "Logan Rogerson", "position": "W", "club": "Wellington Phoenix", "club_league": "A-League"},
        {"name": "Max Mata", "position": "ST", "club": "Shelbourne", "club_league": "League of Ireland"},
        {"name": "Michael Woud", "position": "GK", "club": "Yokohama FC", "club_league": "J-League"},
        {"name": "Sam Sutton", "position": "CB", "club": "Wellington Phoenix", "club_league": "A-League"},
        {"name": "Joe Champness", "position": "W", "club": "Newcastle Jets", "club_league": "A-League"},
    ],
    "Norway": [
        {"name": "Erling Haaland", "position": "ST", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Martin Odegaard", "position": "AM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Sander Berge", "position": "CM", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Alexander Sorloth", "position": "ST", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Oscar Bobb", "position": "W", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Leo Ostigard", "position": "CB", "club": "Rennes", "club_league": "Ligue 1"},
        {"name": "Stefan Strandberg", "position": "CB", "club": "Rosenborg", "club_league": "Eliteserien"},
        {"name": "Birger Meling", "position": "FB", "club": "Rennes", "club_league": "Ligue 1"},
        {"name": "Fredrik Aursnes", "position": "CM", "club": "Benfica", "club_league": "Liga Portugal"},
        {"name": "Mats Moller Daehli", "position": "AM", "club": "Stabæk", "club_league": "Eliteserien"},
        {"name": "Mohamed Elyounoussi", "position": "W", "club": "Copenhagen", "club_league": "Superligaen"},
        {"name": "Julian Ryerson", "position": "FB", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Antonio Nusa", "position": "W", "club": "RB Leipzig", "club_league": "Bundesliga"},
        {"name": "David Moller Wolfe", "position": "FB", "club": "Almere City", "club_league": "Eredivisie"},
        {"name": "Andreas Hanche-Olsen", "position": "CB", "club": "Mainz", "club_league": "Bundesliga"},
        {"name": "Mathias Normann", "position": "CM", "club": "Al-Wakrah", "club_league": "Qatar Stars League"},
        {"name": "Orjan Nyland", "position": "GK", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Andre Hansen", "position": "GK", "club": "Rosenborg", "club_league": "Eliteserien"},
        {"name": "Kristoffer Ajer", "position": "CB", "club": "Brentford", "club_league": "Premier League"},
        {"name": "Morten Thorsby", "position": "CM", "club": "Genoa", "club_league": "Serie A"},
        {"name": "Aron Donnum", "position": "W", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Hugo Vetlesen", "position": "AM", "club": "Club Brugge", "club_league": "Jupiler Pro League"},
        {"name": "Jens Petter Hauge", "position": "W", "club": "Bodo/Glimt", "club_league": "Eliteserien"},
        {"name": "Sander Svendsen", "position": "W", "club": "Odd", "club_league": "Eliteserien"},
        {"name": "Markus Solbakken", "position": "CM", "club": "Venezia", "club_league": "Serie A"},
        {"name": "Isak Hansen-Aaroen", "position": "AM", "club": "Freiburg", "club_league": "Bundesliga"},
    ],
    "Panama": [
        {"name": "Anibal Godoy", "position": "CM", "club": "Nashville SC", "club_league": "MLS"},
        {"name": "Adalberto Carrasquilla", "position": "CM", "club": "Houston Dynamo", "club_league": "MLS"},
        {"name": "Ismael Diaz", "position": "W", "club": "Universidad Catolica", "club_league": "Ecuadorian Serie A"},
        {"name": "Jose Fajardo", "position": "ST", "club": "Universitario", "club_league": "Liga 1 Peru"},
        {"name": "Eric Davis", "position": "FB", "club": "Al-Ettifaq", "club_league": "SPL"},
        {"name": "Fidel Escobar", "position": "CB", "club": "Saprissa", "club_league": "Liga FPD"},
        {"name": "Harold Cummings", "position": "CB", "club": "Al-Fayha", "club_league": "SPL"},
        {"name": "Michael Murillo", "position": "FB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Yoel Barcenas", "position": "W", "club": "Mazatlan", "club_league": "Liga MX"},
        {"name": "Cristian Martinez", "position": "CM", "club": "Cincinnati", "club_league": "MLS"},
        {"name": "Abdiel Ayarza", "position": "W", "club": "Sporting Gijon", "club_league": "La Liga"},
        {"name": "Omar Valencia", "position": "FB", "club": "Saprissa", "club_league": "Liga FPD"},
        {"name": "Ivan Anderson", "position": "FB", "club": "Tauro", "club_league": "LPF"},
        {"name": "Edgar Barcenas", "position": "W", "club": "Cerro Porteno", "club_league": "Paraguayan Primera"},
        {"name": "Alberto Quintero", "position": "W", "club": "Universitario", "club_league": "LPF"},
        {"name": "Jose Luis Rodriguez", "position": "AM", "club": "Gent", "club_league": "Jupiler Pro League"},
        {"name": "Roberto Chen", "position": "CB", "club": "Alcorcon", "club_league": "La Liga"},
        {"name": "Luis Mejia", "position": "GK", "club": "Tauro", "club_league": "LPF"},
        {"name": "Orlando Mosquera", "position": "GK", "club": "Al-Fateh", "club_league": "SPL"},
        {"name": "Cesar Yanis", "position": "W", "club": "Plaza Amador", "club_league": "LPF"},
        {"name": "Roderick Miller", "position": "CB", "club": "Dibba Al-Hisn", "club_league": "UAE Pro League"},
        {"name": "Armando Cooper", "position": "CM", "club": "Tauro", "club_league": "LPF"},
        {"name": "Rolando Blackburn", "position": "ST", "club": "Cerro Porteno", "club_league": "Paraguayan Primera"},
        {"name": "Jose Calderon", "position": "GK", "club": "FAS", "club_league": "LPF"},
        {"name": "Jose Guerra", "position": "CB", "club": "Arabe Unido", "club_league": "LPF"},
        {"name": "Ricardo Buitrago", "position": "CM", "club": "Plaza Amador", "club_league": "LPF"},
    ],
    "Paraguay": [
        {"name": "Miguel Almiron", "position": "W", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Oscar Cardozo", "position": "ST", "club": "Libertad", "club_league": "Paraguayan Primera"},
        {"name": "Antony Silva", "position": "GK", "club": "Cerro Porteno", "club_league": "Paraguayan Primera"},
        {"name": "Gustavo Gomez", "position": "CB", "club": "Palmeiras", "club_league": "Brasileirao"},
        {"name": "Fabian Balbuena", "position": "CB", "club": "Dinamo Moscow", "club_league": "RFPL"},
        {"name": "Junior Alonso", "position": "CB", "club": "Atletico Mineiro", "club_league": "Brasileirao"},
        {"name": "Mathias Villasanti", "position": "CM", "club": "Gremio", "club_league": "Brasileirao"},
        {"name": "Richard Sanchez", "position": "CM", "club": "Olimpia", "club_league": "Paraguayan Primera"},
        {"name": "Angel Romero", "position": "W", "club": "Corinthians", "club_league": "Brasileirao"},
        {"name": "Julio Enciso", "position": "AM", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Adam Bareiro", "position": "ST", "club": "River Plate", "club_league": "Liga Profesional"},
        {"name": "Alejandro Romero Gamarra", "position": "AM", "club": "Al-Taawoun", "club_league": "SPL"},
        {"name": "Ivan Ramirez", "position": "FB", "club": "Libertad", "club_league": "Paraguayan Primera"},
        {"name": "Santiago Arzamendia", "position": "FB", "club": "Estudiantes", "club_league": "Liga Profesional"},
        {"name": "Robert Piris Da Motta", "position": "CM", "club": "Libertad", "club_league": "Paraguayan Primera"},
        {"name": "Hernan Perez", "position": "W", "club": "Libertad", "club_league": "Paraguayan Primera"},
        {"name": "Alfredo Aguilar", "position": "GK", "club": "Guarani", "club_league": "Paraguayan Primera"},
        {"name": "Bruno Valdez", "position": "CB", "club": "Club America", "club_league": "Liga MX"},
        {"name": "Jorge Morel", "position": "CB", "club": "Olimpia", "club_league": "Paraguayan Primera"},
        {"name": "Ramon Sosa", "position": "W", "club": "Talleres", "club_league": "Liga Profesional"},
        {"name": "Diego Gavilan", "position": "CM", "club": "Libertad", "club_league": "Paraguayan Primera"},
        {"name": "Fernando Román", "position": "FB", "club": "Guarani", "club_league": "Paraguayan Primera"},
        {"name": "Luis Caceres", "position": "DM", "club": "Olimpia", "club_league": "Paraguayan Primera"},
        {"name": "Ivan Piris", "position": "FB", "club": "Olimpia", "club_league": "Paraguayan Primera"},
        {"name": "Cecilio Dominguez", "position": "W", "club": "Libertad", "club_league": "Paraguayan Primera"},
        {"name": "Blas Riveros", "position": "CB", "club": "Basel", "club_league": "Swiss Super League"},
    ],
    "Portugal": [
        {"name": "Diogo Costa", "position": "GK", "club": "Porto", "club_league": "Liga Portugal"},
        {"name": "Jose Sa", "position": "GK", "club": "Wolverhampton", "club_league": "Premier League"},
        {"name": "Rui Silva", "position": "GK", "club": "Sporting CP", "club_league": "Liga Portugal"},
        {"name": "Diogo Dalot", "position": "FB", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Nuno Mendes", "position": "FB", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Nelson Semedo", "position": "FB", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Joao Cancelo", "position": "FB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Goncalo Inacio", "position": "CB", "club": "Sporting CP", "club_league": "Liga Portugal"},
        {"name": "Tomas Araujo", "position": "CB", "club": "Benfica", "club_league": "Liga Portugal"},
        {"name": "Ruben Dias", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Renato Veiga", "position": "CB", "club": "Villarreal", "club_league": "La Liga"},
        {"name": "Antonio Silva", "position": "CB", "club": "Benfica", "club_league": "Liga Portugal"},
        {"name": "Ruben Neves", "position": "DM", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Samu Costa", "position": "CM", "club": "Mallorca", "club_league": "La Liga"},
        {"name": "Joao Neves", "position": "CM", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Vitinha", "position": "CM", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Bernardo Silva", "position": "CM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Bruno Fernandes", "position": "AM", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Joao Felix", "position": "AM", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Trincao", "position": "W", "club": "Sporting CP", "club_league": "Liga Portugal"},
        {"name": "Francisco Conceicao", "position": "W", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Pedro Neto", "position": "W", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Rafael Leao", "position": "W", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Andre Gomes", "position": "W", "club": "Real Sociedad", "club_league": "La Liga"},
        {"name": "Goncalo Ramos", "position": "ST", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Cristiano Ronaldo", "position": "ST", "club": "Al-Nassr", "club_league": "SPL"},
    ],
    "Qatar": [
        {"name": "Akram Afif", "position": "W", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Almoez Ali", "position": "ST", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Hassan Al-Haydos", "position": "AM", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Boualem Khoukhi", "position": "CB", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Abdelkarim Hassan", "position": "FB", "club": "Al-Wakrah", "club_league": "Qatar Stars League"},
        {"name": "Tarek Salman", "position": "CB", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Karim Boudiaf", "position": "CM", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Assim Madibo", "position": "CM", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Ahmed Fathi", "position": "FB", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Ismael Mohammad", "position": "FB", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Mohammed Muntari", "position": "ST", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Yusuf Abdurisag", "position": "W", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Ahmed Alaaeldin", "position": "ST", "club": "Al-Gharafa", "club_league": "Qatar Stars League"},
        {"name": "Meshaal Barsham", "position": "GK", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Saad Al-Sheeb", "position": "GK", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Saud Al-Hajri", "position": "GK", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Pedro Miguel", "position": "FB", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Bassam Al-Rawi", "position": "CB", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Mahdi Salem", "position": "CB", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Mostafa Tarek", "position": "W", "club": "Al-Gharafa", "club_league": "Qatar Stars League"},
        {"name": "Homam El Ahmed", "position": "CM", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Hazem Shehata", "position": "CM", "club": "Al-Wakrah", "club_league": "Qatar Stars League"},
        {"name": "Suliman Al-Hamid", "position": "CB", "club": "Al-Rayyan", "club_league": "Qatar Stars League"},
        {"name": "Ahmed Al-Sayed", "position": "CB", "club": "Al-Sadd", "club_league": "Qatar Stars League"},
        {"name": "Mohammed Emam", "position": "CM", "club": "Al-Duhail", "club_league": "Qatar Stars League"},
        {"name": "Khalid Muneer", "position": "W", "club": "Al-Wakrah", "club_league": "Qatar Stars League"},
    ],
    "Saudi Arabia": [
        {"name": "Salem Al-Dawsari", "position": "W", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Firas Al-Buraikan", "position": "ST", "club": "Al-Ahli", "club_league": "SPL"},
        {"name": "Sultan Al-Ghannam", "position": "FB", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Yasser Al-Shahrani", "position": "FB", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Ali Al-Bulaihi", "position": "CB", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Abdullah Otayf", "position": "CM", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Salman Al-Faraj", "position": "CM", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Mohammed Kanno", "position": "CM", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Nawaf Al-Aqidi", "position": "GK", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Mohammed Al-Owais", "position": "GK", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Abdulelah Al-Malki", "position": "CM", "club": "Al-Ittihad", "club_league": "SPL"},
        {"name": "Hattan Bahebri", "position": "W", "club": "Al-Shabab", "club_league": "SPL"},
        {"name": "Abdullah Radif", "position": "ST", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Nasser Al-Dawsari", "position": "CM", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Ahmed Bamsaud", "position": "FB", "club": "Al-Ittihad", "club_league": "SPL"},
        {"name": "Hassan Kadesh", "position": "CB", "club": "Al-Ittihad", "club_league": "SPL"},
        {"name": "Moteb Al-Harbi", "position": "FB", "club": "Al-Ittihad", "club_league": "SPL"},
        {"name": "Fahad Al-Muwallad", "position": "W", "club": "Al-Ittihad", "club_league": "SPL"},
        {"name": "Sami Al-Najei", "position": "AM", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Ayman Yahya", "position": "W", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Abdulrahman Al-Aboud", "position": "W", "club": "Al-Ittihad", "club_league": "SPL"},
        {"name": "Marwan Al-Sahan", "position": "CB", "club": "Al-Shabab", "club_league": "SPL"},
        {"name": "Riyadh Sharahili", "position": "DM", "club": "Al-Tai", "club_league": "SPL"},
        {"name": "Abdullah Al-Hamdan", "position": "ST", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Saud Abdulhamid", "position": "FB", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Mohammed Al-Breik", "position": "FB", "club": "Al-Hilal", "club_league": "SPL"},
    ],
    "Scotland": [
        {"name": "Andy Robertson", "position": "FB", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Scott McTominay", "position": "CM", "club": "Napoli", "club_league": "Serie A"},
        {"name": "John McGinn", "position": "CM", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Kieran Tierney", "position": "FB", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Lyndon Dykes", "position": "ST", "club": "QPR", "club_league": "EFL Championship"},
        {"name": "Che Adams", "position": "ST", "club": "Torino", "club_league": "Serie A"},
        {"name": "Ryan Christie", "position": "AM", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Stuart Armstrong", "position": "CM", "club": "Vancouver Whitecaps", "club_league": "MLS"},
        {"name": "Grant Hanley", "position": "CB", "club": "Norwich", "club_league": "EFL Championship"},
        {"name": "Jack Hendry", "position": "CB", "club": "Al-Ettifaq", "club_league": "SPL"},
        {"name": "Liam Cooper", "position": "CB", "club": "Leeds", "club_league": "EFL Championship"},
        {"name": "Lewis Ferguson", "position": "AM", "club": "Bologna", "club_league": "Serie A"},
        {"name": "Nathan Patterson", "position": "FB", "club": "Everton", "club_league": "Premier League"},
        {"name": "Billy Gilmour", "position": "CM", "club": "Napoli", "club_league": "Serie A"},
        {"name": "Aaron Hickey", "position": "FB", "club": "Brentford", "club_league": "Premier League"},
        {"name": "David Turnbull", "position": "AM", "club": "Cardiff", "club_league": "EFL Championship"},
        {"name": "Angus Gunn", "position": "GK", "club": "Norwich", "club_league": "EFL Championship"},
        {"name": "Craig Gordon", "position": "GK", "club": "Hearts", "club_league": "Scottish Premiership"},
        {"name": "Zander Clark", "position": "GK", "club": "Hearts", "club_league": "Scottish Premiership"},
        {"name": "Scott McKenna", "position": "CB", "club": "Copenhagen", "club_league": "Superligaen"},
        {"name": "Anthony Ralston", "position": "FB", "club": "Celtic", "club_league": "Scottish Premiership"},
        {"name": "Kenny McLean", "position": "CM", "club": "Norwich", "club_league": "EFL Championship"},
        {"name": "Jacob Brown", "position": "W", "club": "Luton", "club_league": "EFL Championship"},
        {"name": "Josh Doig", "position": "FB", "club": "Verona", "club_league": "Serie A"},
        {"name": "Lewis Morgan", "position": "W", "club": "New York Red Bulls", "club_league": "MLS"},
        {"name": "Ross McCrorie", "position": "CM", "club": "Bristol City", "club_league": "EFL Championship"},
    ],
    "Senegal": [
        {"name": "Sadio Mane", "position": "W", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Kalidou Koulibaly", "position": "CB", "club": "Al-Hilal", "club_league": "SPL"},
        {"name": "Ismaila Sarr", "position": "W", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Nicolas Jackson", "position": "ST", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Pape Gueye", "position": "CM", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Idrissa Gueye", "position": "DM", "club": "Everton", "club_league": "Premier League"},
        {"name": "Fode Ballo-Toure", "position": "FB", "club": "Brentford", "club_league": "Premier League"},
        {"name": "Youssouf Sabaly", "position": "FB", "club": "Betis", "club_league": "La Liga"},
        {"name": "Abdou Diallo", "position": "CB", "club": "Al-Arabi", "club_league": "Qatar Stars League"},
        {"name": "Boulaye Dia", "position": "ST", "club": "Lazio", "club_league": "Serie A"},
        {"name": "Cheikhou Kouyate", "position": "CM", "club": "Nottingham Forest", "club_league": "Premier League"},
        {"name": "Moussa Wague", "position": "FB", "club": "Gorica", "club_league": "HNL"},
        {"name": "Papa Gueye", "position": "CM", "club": "Krylya Sovetov", "club_league": "RFPL"},
        {"name": "Bamba Dieng", "position": "ST", "club": "Lorient", "club_league": "Ligue 1"},
        {"name": "Mamadou Loum", "position": "CM", "club": "Rayo Vallecano", "club_league": "La Liga"},
        {"name": "Formose Mendy", "position": "CB", "club": "Amiens", "club_league": "Ligue 2"},
        {"name": "Edouard Mendy", "position": "GK", "club": "Al-Ahli", "club_league": "SPL"},
        {"name": "Alfred Gomis", "position": "GK", "club": "Rennes", "club_league": "Ligue 1"},
        {"name": "Mbaye Diagne", "position": "ST", "club": "Caykur Rizespor", "club_league": "Super Lig"},
        {"name": "Iliman Ndiaye", "position": "AM", "club": "Everton", "club_league": "Premier League"},
        {"name": "Habib Diallo", "position": "ST", "club": "Al-Shabab", "club_league": "SPL"},
        {"name": "Nampalys Mendy", "position": "CM", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Saliou Ciss", "position": "FB", "club": "Angers", "club_league": "Ligue 1"},
        {"name": "Mamadou Niang", "position": "ST", "club": "Al-Jazira", "club_league": "UAE Pro League"},
        {"name": "Moussa Konate", "position": "ST", "club": "Dijon", "club_league": "Ligue 2"},
        {"name": "Papa Ndiaye", "position": "CM", "club": "Dakar Sacre-Coeur", "club_league": "Senegal Ligue 1"},
    ],
    "South Africa": [
        {"name": "Percy Tau", "position": "W", "club": "Al-Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Lyle Foster", "position": "ST", "club": "Burnley", "club_league": "EFL Championship"},
        {"name": "Themba Zwane", "position": "AM", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Ronwen Williams", "position": "GK", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Grant Kekana", "position": "CB", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Mothobi Mvala", "position": "CB", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Nyiko Mobbie", "position": "FB", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Teboho Mokoena", "position": "CM", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Sphephelo Sithole", "position": "CM", "club": "Tondela", "club_league": "Liga Portugal"},
        {"name": "Evidence Makgopa", "position": "ST", "club": "Orlando Pirates", "club_league": "PSL"},
        {"name": "Zakhele Lepasa", "position": "ST", "club": "Orlando Pirates", "club_league": "PSL"},
        {"name": "Khuliso Mudau", "position": "FB", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Aubrey Modiba", "position": "FB", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Siphiwe Tshabalala", "position": "W", "club": "Kaizer Chiefs", "club_league": "PSL"},
        {"name": "Luther Singh", "position": "W", "club": "Sassuolo", "club_league": "Serie A"},
        {"name": "Kamohelo Mahlatsi", "position": "AM", "club": "Kaizer Chiefs", "club_league": "PSL"},
        {"name": "Siyanda Xulu", "position": "CB", "club": "Hapoel Tel Aviv", "club_league": "Israeli Premier League"},
        {"name": "Rushine De Reuck", "position": "CB", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Dean Furman", "position": "CM", "club": "Carlisle", "club_league": "EFL Championship"},
        {"name": "Bongani Zungu", "position": "CM", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Luke le Roux", "position": "CM", "club": "Salernitana", "club_league": "Serie A"},
        {"name": "Oswin Appollis", "position": "W", "club": "Supersport United", "club_league": "PSL"},
        {"name": "Njabulo Ngcobo", "position": "CB", "club": "Kaizer Chiefs", "club_league": "PSL"},
        {"name": "Thibang Phete", "position": "CB", "club": "Bahia", "club_league": "Brasileirao"},
        {"name": "Lyle Lakay", "position": "FB", "club": "Mamelodi Sundowns", "club_league": "PSL"},
        {"name": "Fagrie Lakay", "position": "W", "club": "Pyramids", "club_league": "Egyptian Premier League"},
    ],
    "South Korea": [
        {"name": "Son Heung-min", "position": "W", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Lee Kang-in", "position": "AM", "club": "PSG", "club_league": "Ligue 1"},
        {"name": "Kim Min-jae", "position": "CB", "club": "Bayern Munich", "club_league": "Bundesliga"},
        {"name": "Hwang Hee-chan", "position": "W", "club": "Wolves", "club_league": "Premier League"},
        {"name": "Lee Jae-sung", "position": "AM", "club": "Mainz", "club_league": "Bundesliga"},
        {"name": "Jo Hyeon-woo", "position": "GK", "club": "Ulsan HD", "club_league": "K-League"},
        {"name": "Kim Seung-gyu", "position": "GK", "club": "Al-Shabab", "club_league": "SPL"},
        {"name": "Kim Jin-su", "position": "FB", "club": "Jeonbuk", "club_league": "K-League"},
        {"name": "Jung Seung-hyun", "position": "CB", "club": "Al-Wakrah", "club_league": "Qatar Stars League"},
        {"name": "Park Yong-woo", "position": "DM", "club": "Al-Ain", "club_league": "UAE Pro League"},
        {"name": "Hwang In-beom", "position": "CM", "club": "Feyenoord", "club_league": "Eredivisie"},
        {"name": "Hong Hyun-seok", "position": "AM", "club": "Mainz", "club_league": "Bundesliga"},
        {"name": "Oh Se-hun", "position": "ST", "club": "Ulsan HD", "club_league": "K-League"},
        {"name": "Cho Gue-sung", "position": "ST", "club": "Midtjylland", "club_league": "Superligaen"},
        {"name": "Jeong Woo-yeong", "position": "W", "club": "Stuttgart", "club_league": "Bundesliga"},
        {"name": "Seol Young-woo", "position": "FB", "club": "Zvezda", "club_league": "Serbian SuperLiga"},
        {"name": "Kwon Kyung-won", "position": "CB", "club": "Gwangju FC", "club_league": "K-League"},
        {"name": "Paik Seung-ho", "position": "CM", "club": "Birmingham", "club_league": "EFL Championship"},
        {"name": "Yang Hyun-jun", "position": "W", "club": "Celtic", "club_league": "Scottish Premiership"},
        {"name": "Bae Jun-ho", "position": "W", "club": "Stoke", "club_league": "EFL Championship"},
        {"name": "Song Min-kyu", "position": "W", "club": "Jeonbuk", "club_league": "K-League"},
        {"name": "Kwon Hwang-kwun", "position": "CB", "club": "Daejeon Hana", "club_league": "K-League"},
        {"name": "Eom Ji-sung", "position": "W", "club": "Gwangju FC", "club_league": "K-League"},
        {"name": "Kim Young-gwon", "position": "CB", "club": "Ulsan HD", "club_league": "K-League"},
        {"name": "Lee Myung-jae", "position": "FB", "club": "Ulsan HD", "club_league": "K-League"},
        {"name": "Park Ji-sung", "position": "CM", "club": "Jeonbuk Hyundai", "club_league": "K-League"},
    ],
    "Spain": [
        {"name": "Unai Simon", "position": "GK", "club": "Athletic Bilbao", "club_league": "La Liga"},
        {"name": "David Raya", "position": "GK", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Joan Garcia", "position": "GK", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Pau Cubarsi", "position": "CB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Robin Le Normand", "position": "CB", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Aymeric Laporte", "position": "CB", "club": "Athletic Bilbao", "club_league": "La Liga"},
        {"name": "Eric Garcia", "position": "CB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Pedro Porro", "position": "FB", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Marcos Llorente", "position": "FB", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Alejandro Grimaldo", "position": "FB", "club": "Bayer Leverkusen", "club_league": "Bundesliga"},
        {"name": "Marc Cucurella", "position": "FB", "club": "Chelsea", "club_league": "Premier League"},
        {"name": "Rodri", "position": "DM", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Martin Zubimendi", "position": "DM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Gavi", "position": "CM", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Pedri", "position": "CM", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Fabian Ruiz", "position": "CM", "club": "Paris Saint-Germain", "club_league": "Ligue 1"},
        {"name": "Mikel Merino", "position": "CM", "club": "Arsenal", "club_league": "Premier League"},
        {"name": "Dani Olmo", "position": "AM", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Alex Baena", "position": "AM", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Lamine Yamal", "position": "W", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Ferran Torres", "position": "W", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Yeremy Pino", "position": "W", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Nico Williams", "position": "W", "club": "Athletic Bilbao", "club_league": "La Liga"},
        {"name": "Sergio Munoz", "position": "W", "club": "Osasuna", "club_league": "La Liga"},
        {"name": "Mikel Oyarzabal", "position": "W", "club": "Real Sociedad", "club_league": "La Liga"},
        {"name": "Borja Iglesias", "position": "ST", "club": "Celta Vigo", "club_league": "La Liga"},
    ],
    "Sweden": [
        {"name": "Alexander Isak", "position": "ST", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Dejan Kulusevski", "position": "W", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Viktor Gyokeres", "position": "ST", "club": "Sporting CP", "club_league": "Liga Portugal"},
        {"name": "Emil Forsberg", "position": "AM", "club": "New York RB", "club_league": "MLS"},
        {"name": "Victor Lindelof", "position": "CB", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Andreas Christensen", "position": "CB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Emil Krafth", "position": "FB", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Ludwig Augustinsson", "position": "FB", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Mattias Svanberg", "position": "CM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Hugo Larsson", "position": "CM", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Jesper Karlsson", "position": "W", "club": "Bologna", "club_league": "Serie A"},
        {"name": "Anthony Elanga", "position": "W", "club": "Nottingham Forest", "club_league": "Premier League"},
        {"name": "Robin Olsen", "position": "GK", "club": "Aston Villa", "club_league": "Premier League"},
        {"name": "Karl-Johan Johnsson", "position": "GK", "club": "Bordeaux", "club_league": "Ligue 2"},
        {"name": "Isak Hien", "position": "CB", "club": "Atalanta", "club_league": "Serie A"},
        {"name": "Joel Andersson", "position": "FB", "club": "Mainz", "club_league": "Bundesliga"},
        {"name": "Ken Sema", "position": "W", "club": "Watford", "club_league": "EFL Championship"},
        {"name": "Sebastian Nanasi", "position": "AM", "club": "Strasbourg", "club_league": "Ligue 1"},
        {"name": "Benjamin Nygren", "position": "W", "club": "Genk", "club_league": "Jupiler Pro League"},
        {"name": "Gustaf Lagerbielke", "position": "CB", "club": "Celtic", "club_league": "Scottish Premiership"},
        {"name": "Karl Gustafsson", "position": "CM", "club": "Elfsborg", "club_league": "Allsvenskan"},
        {"name": "Oscar Hiljemark", "position": "CM", "club": "Aalborg", "club_league": "Superligaen"},
        {"name": "Linus Wahlqvist", "position": "FB", "club": "Djurgarden", "club_league": "Allsvenskan"},
        {"name": "Oliver Edvardsen", "position": "W", "club": "Go Ahead Eagles", "club_league": "Eredivisie"},
        {"name": "Isak Pettersson", "position": "GK", "club": "Elfsborg", "club_league": "Allsvenskan"},
        {"name": "Noah Persson", "position": "FB", "club": "Lillestrom", "club_league": "Eliteserien"},
    ],
    "Switzerland": [
        {"name": "Granit Xhaka", "position": "CM", "club": "Leverkusen", "club_league": "Bundesliga"},
        {"name": "Manuel Akanji", "position": "CB", "club": "Manchester City", "club_league": "Premier League"},
        {"name": "Xherdan Shaqiri", "position": "AM", "club": "Chicago Fire", "club_league": "MLS"},
        {"name": "Ricardo Rodriguez", "position": "FB", "club": "Torino", "club_league": "Serie A"},
        {"name": "Fabian Schar", "position": "CB", "club": "Newcastle", "club_league": "Premier League"},
        {"name": "Yann Sommer", "position": "GK", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Denis Zakaria", "position": "CM", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Breel Embolo", "position": "ST", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Haris Seferovic", "position": "ST", "club": "Al-Wahda", "club_league": "UAE Pro League"},
        {"name": "Steven Zuber", "position": "W", "club": "AEK Athens", "club_league": "Super League"},
        {"name": "Remo Freuler", "position": "CM", "club": "Bologna", "club_league": "Serie A"},
        {"name": "Michel Aebischer", "position": "FB", "club": "Bologna", "club_league": "Serie A"},
        {"name": "Silvan Widmer", "position": "FB", "club": "Mainz", "club_league": "Bundesliga"},
        {"name": "Nico Elvedi", "position": "CB", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Djibril Sow", "position": "CM", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Ruben Vargas", "position": "W", "club": "Sevilla", "club_league": "La Liga"},
        {"name": "Zuber", "position": "W", "club": "AEK Athens", "club_league": "Super League"},
        {"name": "Jonas Omlin", "position": "GK", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Gregor Kobel", "position": "GK", "club": "Dortmund", "club_league": "Bundesliga"},
        {"name": "Eray Comert", "position": "CB", "club": "Nantes", "club_league": "Ligue 1"},
        {"name": "Andi Zeqiri", "position": "ST", "club": "Gent", "club_league": "Jupiler Pro League"},
        {"name": "Kwadwo Duah", "position": "ST", "club": "Ludogorets", "club_league": "Bulgarian First League"},
        {"name": "Vincent Sierro", "position": "CM", "club": "Toulouse", "club_league": "Ligue 1"},
        {"name": "Philipp Kohn", "position": "GK", "club": "Salzburg", "club_league": "Austrian Bundesliga"},
        {"name": "Ulisses Garcia", "position": "FB", "club": "Marseille", "club_league": "Ligue 1"},
        {"name": "Dan Ndoye", "position": "W", "club": "Bologna", "club_league": "Serie A"},
    ],
    "Tunisia": [
        {"name": "Wahbi Khazri", "position": "AM", "club": "Al-Shabab", "club_league": "SPL"},
        {"name": "Youssef Msakni", "position": "W", "club": "Al-Arabi", "club_league": "Qatar Stars League"},
        {"name": "Ali Maaloul", "position": "FB", "club": "Al Ahly", "club_league": "Egyptian Premier League"},
        {"name": "Dylan Bronn", "position": "CB", "club": "Salernitana", "club_league": "Serie A"},
        {"name": "Montassar Talbi", "position": "CB", "club": "Lorient", "club_league": "Ligue 1"},
        {"name": "Aissa Laidouni", "position": "CM", "club": "Al-Wakrah", "club_league": "Qatar Stars League"},
        {"name": "Ellyes Skhiri", "position": "CM", "club": "Ein Frankfurt", "club_league": "Bundesliga"},
        {"name": "Nader Ghandri", "position": "CB", "club": "Club Africain", "club_league": "Tunisian Ligue 1"},
        {"name": "Hannibal Mejbri", "position": "AM", "club": "Burnley", "club_league": "EFL Championship"},
        {"name": "Anis Ben Slimane", "position": "W", "club": "Verona", "club_league": "Serie A"},
        {"name": "Taha Yassine Khenissi", "position": "ST", "club": "Al-Khor", "club_league": "Qatar Stars League"},
        {"name": "Seifeddine Jaziri", "position": "ST", "club": "Zamalek", "club_league": "Egyptian Premier League"},
        {"name": "Mortadha Ben Ouanes", "position": "W", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Amine Ben Rejeb", "position": "FB", "club": "Etoile du Sahel", "club_league": "Tunisian Ligue 1"},
        {"name": "Bechir Ben Said", "position": "GK", "club": "Esperance", "club_league": "Tunisian Ligue 1"},
        {"name": "Moez Ben Cherifia", "position": "GK", "club": "Esperance", "club_league": "Tunisian Ligue 1"},
        {"name": "Mohamed Ali Ben Romdhane", "position": "CM", "club": "Ferencvaros", "club_league": "NB I"},
        {"name": "Ghailene Chaalali", "position": "CM", "club": "Esperance", "club_league": "Tunisian Ligue 1"},
        {"name": "Firas Chaouat", "position": "ST", "club": "Etoile du Sahel", "club_league": "Tunisian Ligue 1"},
        {"name": "Rami Bedoui", "position": "CB", "club": "Esperance", "club_league": "Tunisian Ligue 1"},
        {"name": "Yassine Meriah", "position": "CB", "club": "Kasimpasa", "club_league": "Super Lig"},
        {"name": "Naïm Sliti", "position": "W", "club": "Al-Ahli", "club_league": "SPL"},
        {"name": "Sayfallah Ltaief", "position": "W", "club": "Lugano", "club_league": "Swiss Super League"},
        {"name": "Ali Abdi", "position": "FB", "club": "Caen", "club_league": "Ligue 2"},
        {"name": "Mohamed Amine Ben Hamida", "position": "CB", "club": "Esperance", "club_league": "Tunisian Ligue 1"},
        {"name": "Ahmed Khalil", "position": "GK", "club": "Club Africain", "club_league": "Tunisian Ligue 1"},
    ],
    "Turkey": [
        {"name": "Hakan Calhanoglu", "position": "CM", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Arda Guler", "position": "AM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Cengiz Under", "position": "W", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Yusuf Yazici", "position": "AM", "club": "CSKA Moscow", "club_league": "RFPL"},
        {"name": "Caglar Soyuncu", "position": "CB", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Merih Demiral", "position": "CB", "club": "Al-Ahli", "club_league": "SPL"},
        {"name": "Zeki Celik", "position": "FB", "club": "Roma", "club_league": "Serie A"},
        {"name": "Ferdi Kadioglu", "position": "FB", "club": "Brighton", "club_league": "Premier League"},
        {"name": "Kenan Yildiz", "position": "W", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Orkun Kokcu", "position": "CM", "club": "Benfica", "club_league": "Liga Portugal"},
        {"name": "Irfan Can Kahveci", "position": "AM", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Baris Alper Yilmaz", "position": "W", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Enes Unal", "position": "ST", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Kerem Akturkoglu", "position": "W", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Mert Gunok", "position": "GK", "club": "Besiktas", "club_league": "Super Lig"},
        {"name": "Ugurcan Cakir", "position": "GK", "club": "Trabzonspor", "club_league": "Super Lig"},
        {"name": "Ozan Kabak", "position": "CB", "club": "Hoffenheim", "club_league": "Bundesliga"},
        {"name": "Samet Akaydin", "position": "CB", "club": "Fenerbahce", "club_league": "Super Lig"},
        {"name": "Abdulkerim Bardakci", "position": "CB", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Salih Ozcan", "position": "CM", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "Kaan Ayhan", "position": "FB", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Yunus Akgun", "position": "W", "club": "Galatasaray", "club_league": "Super Lig"},
        {"name": "Cenk Tosun", "position": "ST", "club": "Besiktas", "club_league": "Super Lig"},
        {"name": "Okay Yokuslu", "position": "DM", "club": "Trabzonspor", "club_league": "Super Lig"},
        {"name": "Tayyip Talha Sanuc", "position": "CB", "club": "Al-Ahli", "club_league": "SPL"},
        {"name": "Altay Bayindir", "position": "GK", "club": "Manchester United", "club_league": "Premier League"},
    ],
    "United States": [
        {"name": "Christian Pulisic", "position": "W", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Weston McKennie", "position": "CM", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Giovanni Reyna", "position": "AM", "club": "Borussia Dortmund", "club_league": "Bundesliga"},
        {"name": "Tim Weah", "position": "W", "club": "Juventus", "club_league": "Serie A"},
        {"name": "Folarin Balogun", "position": "ST", "club": "Monaco", "club_league": "Ligue 1"},
        {"name": "Antonee Robinson", "position": "FB", "club": "Fulham", "club_league": "Premier League"},
        {"name": "Tyler Adams", "position": "DM", "club": "Bournemouth", "club_league": "Premier League"},
        {"name": "Yunus Musah", "position": "CM", "club": "AC Milan", "club_league": "Serie A"},
        {"name": "Chris Richards", "position": "CB", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Matt Turner", "position": "GK", "club": "Crystal Palace", "club_league": "Premier League"},
        {"name": "Sergino Dest", "position": "FB", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Cameron Carter-Vickers", "position": "CB", "club": "Celtic", "club_league": "Scottish Premiership"},
        {"name": "Brenden Aaronson", "position": "AM", "club": "Leeds", "club_league": "EFL Championship"},
        {"name": "Ricardo Pepi", "position": "ST", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Haji Wright", "position": "ST", "club": "Coventry", "club_league": "EFL Championship"},
        {"name": "Malik Tillman", "position": "AM", "club": "PSV", "club_league": "Eredivisie"},
        {"name": "Joe Scally", "position": "FB", "club": "M'gladbach", "club_league": "Bundesliga"},
        {"name": "Josh Sargent", "position": "ST", "club": "Norwich", "club_league": "EFL Championship"},
        {"name": "Auston Trusty", "position": "CB", "club": "Sheffield United", "club_league": "EFL Championship"},
        {"name": "Gianluca Busio", "position": "CM", "club": "Venezia", "club_league": "Serie A"},
        {"name": "Ethan Horvath", "position": "GK", "club": "Cardiff", "club_league": "EFL Championship"},
        {"name": "Mark McKenzie", "position": "CB", "club": "Genk", "club_league": "Jupiler Pro League"},
        {"name": "Paxton Pomykal", "position": "CM", "club": "FC Dallas", "club_league": "MLS"},
        {"name": "Kevin Paredes", "position": "W", "club": "Wolfsburg", "club_league": "Bundesliga"},
        {"name": "James Sands", "position": "CB", "club": "St. Pauli", "club_league": "Bundesliga"},
        {"name": "Sean Johnson", "position": "GK", "club": "Toronto FC", "club_league": "MLS"},
    ],
    "Uruguay": [
        {"name": "Federico Valverde", "position": "CM", "club": "Real Madrid", "club_league": "La Liga"},
        {"name": "Darwin Nunez", "position": "ST", "club": "Liverpool", "club_league": "Premier League"},
        {"name": "Ronald Araujo", "position": "CB", "club": "Barcelona", "club_league": "La Liga"},
        {"name": "Jose Gimenez", "position": "CB", "club": "Atletico Madrid", "club_league": "La Liga"},
        {"name": "Rodrigo Bentancur", "position": "CM", "club": "Tottenham", "club_league": "Premier League"},
        {"name": "Luis Suarez", "position": "ST", "club": "Inter Miami", "club_league": "MLS"},
        {"name": "Edinson Cavani", "position": "ST", "club": "Boca Juniors", "club_league": "Liga Profesional"},
        {"name": "Matias Vina", "position": "FB", "club": "Flamengo", "club_league": "Brasileirao"},
        {"name": "Nahitan Nandez", "position": "CM", "club": "Al-Qadsiah", "club_league": "SPL"},
        {"name": "Giorgian De Arrascaeta", "position": "AM", "club": "Flamengo", "club_league": "Brasileirao"},
        {"name": "Facundo Torres", "position": "W", "club": "Orlando City", "club_league": "MLS"},
        {"name": "Maximiliano Araujo", "position": "FB", "club": "Sporting CP", "club_league": "Liga Portugal"},
        {"name": "Sebastian Caceres", "position": "CB", "club": "Club America", "club_league": "Liga MX"},
        {"name": "Manuel Ugarte", "position": "DM", "club": "Manchester United", "club_league": "Premier League"},
        {"name": "Nicolas De La Cruz", "position": "AM", "club": "River Plate", "club_league": "Liga Profesional"},
        {"name": "Sergio Rochet", "position": "GK", "club": "Inter Milan", "club_league": "Serie A"},
        {"name": "Martin Campana", "position": "GK", "club": "Penarol", "club_league": "Liga Profesional"},
        {"name": "Mathias Olivera", "position": "FB", "club": "Napoli", "club_league": "Serie A"},
        {"name": "Agustin Canobbio", "position": "W", "club": "Athletico Paranaense", "club_league": "Brasileirao"},
        {"name": "Brian Rodriguez", "position": "W", "club": "Club America", "club_league": "Liga MX"},
        {"name": "Damian Suarez", "position": "FB", "club": "Gremio", "club_league": "Brasileirao"},
        {"name": "Jonathan Rodriguez", "position": "ST", "club": "Club America", "club_league": "Liga MX"},
        {"name": "Leandro Cabrera", "position": "CB", "club": "Espanyol", "club_league": "La Liga"},
        {"name": "Agustin Alvarez Martinez", "position": "ST", "club": "Sassuolo", "club_league": "Serie A"},
        {"name": "Matias Vecino", "position": "CM", "club": "Lazio", "club_league": "Serie A"},
        {"name": "Joaquin Piquerez", "position": "FB", "club": "Palmeiras", "club_league": "Brasileirao"},
    ],
    "Uzbekistan": [
        {"name": "Eldor Shomurodov", "position": "ST", "club": "Cagliari", "club_league": "Serie A"},
        {"name": "Abdukodir Khusanov", "position": "CB", "club": "Lens", "club_league": "Ligue 1"},
        {"name": "Jaloliddin Masharipov", "position": "W", "club": "Al-Nassr", "club_league": "SPL"},
        {"name": "Otabek Shukurov", "position": "CM", "club": "Al-Wahda", "club_league": "UAE Pro League"},
        {"name": "Husamiddin Aliqulov", "position": "CB", "club": "Cagliari", "club_league": "Serie A"},
        {"name": "Sardor Rashidov", "position": "W", "club": "Navbahor", "club_league": "Uzbekistan Super League"},
        {"name": "Dostonbek Tursunov", "position": "FB", "club": "Pakhtakor", "club_league": "Uzbekistan Super League"},
        {"name": "Bobir Abdixolikov", "position": "ST", "club": "Nasaf", "club_league": "Uzbekistan Super League"},
        {"name": "Akram Djurabaev", "position": "CM", "club": "Pakhtakor", "club_league": "Uzbekistan Super League"},
        {"name": "Ikhsanov Doston", "position": "CB", "club": "Nasaf", "club_league": "Uzbekistan Super League"},
        {"name": "Jasur Khasanov", "position": "CM", "club": "Nasaf", "club_league": "Uzbekistan Super League"},
        {"name": "Sukhrob Nurullaev", "position": "W", "club": "Pakhtakor", "club_league": "Uzbekistan Super League"},
        {"name": "Oybek Turgunov", "position": "FB", "club": "Nasaf", "club_league": "Uzbekistan Super League"},
        {"name": "Umarali Rakhmonaliev", "position": "AM", "club": "Pakhtakor", "club_league": "Uzbekistan Super League"},
        {"name": "Utkir Yusupov", "position": "GK", "club": "Nasaf", "club_league": "Uzbekistan Super League"},
        {"name": "Abbosbek Fayzullaev", "position": "W", "club": "CSKA Moscow", "club_league": "RFPL"},
        {"name": "Mukhammadkodir Khamraliev", "position": "FB", "club": "Pakhtakor", "club_league": "Uzbekistan Super League"},
        {"name": "Sardor Sabirkhodjaev", "position": "AM", "club": "Al-Wakrah", "club_league": "Qatar Stars League"},
        {"name": "Zabikhillo Urinboev", "position": "ST", "club": "Andijon", "club_league": "Uzbekistan Super League"},
        {"name": "Khurshid Giyasov", "position": "CB", "club": "Pakhtakor", "club_league": "Uzbekistan Super League"},
        {"name": "Sukhrob Erkinov", "position": "CM", "club": "Nasaf", "club_league": "Uzbekistan Super League"},
        {"name": "Sanjar Shoakhmedov", "position": "GK", "club": "Pakhtakor", "club_league": "Uzbekistan Super League"},
        {"name": "Dostonbek Hamdamov", "position": "AM", "club": "Bunyodkor", "club_league": "Uzbekistan Super League"},
        {"name": "Jasurbek Yuldashev", "position": "CM", "club": "Bunyodkor", "club_league": "Uzbekistan Super League"},
        {"name": "Sardor Mirzayev", "position": "AM", "club": "Lokomotiv Tashkent", "club_league": "Uzbekistan Super League"},
        {"name": "Bobir Tursunmatov", "position": "GK", "club": "Nasaf", "club_league": "Uzbekistan Super League"},
    ],
}

# ── Big-5 league helpers ──────────────────────────────────────────────────

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


# ── Squad access helpers ──────────────────────────────────────────────────

def get_all_teams() -> list[str]:
    """Return all 48 World Cup team names."""
    teams: list[str] = []
    for group_teams in GROUPS.values():
        teams.extend(group_teams)
    return teams


def get_team_group(team: str) -> str | None:
    """Return the group letter for a team, or None if not found."""
    for letter, teams in GROUPS.items():
        if team in teams:
            return letter
    return None


def get_squad(team: str) -> list[SquadPlayer]:
    """Return the squad for a team as a list of SquadPlayer dataclasses."""
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
    """Check if a league name is a Big-5 European league."""
    return league_name in BIG5_LEAGUES or league_name in BIG5_LEAGUE_ALIASES


def enrich_squad_with_ratings(
    squad: list[SquadPlayer],
    ratings_df,  # pd.DataFrame
) -> list[SquadPlayer]:
    """Enrich squad players with ratings from the optimized ratings data.

    Matches by player name (exact -> case-insensitive -> last-name substring).
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