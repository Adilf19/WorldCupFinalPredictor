"""Reference data for the Spain–Argentina 2026 FIFA World Cup final.

Squads are based on FIFA's confirmed tournament squad announcements. Argentina's
Marcos Senesi entry reflects the official injury replacement for Leonardo Balerdi.

Sources:
https://www.fifa.com/en/articles/spain-squad-announcement-luis-de-la-fuente
https://www.fifa.com/es/tournaments/mens/worldcup/canadamexicousa2026/articles/lista-convocados-seleccion-argentina-para-la-copa-mundial-2026
https://www.fifa.com/es/tournaments/mens/worldcup/canadamexicousa2026/articles/leonardo-balerdi-baja-copa-mundial-argentina
https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/final-live-watch-teams-tickets
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PlayerSeed:
    """Stable player identity fields suitable for reference-data seeding."""

    name: str
    position: str


@dataclass(frozen=True, slots=True)
class TeamSeed:
    """A national team, manager, and tournament squad."""

    name: str
    country: str
    manager: str
    players: tuple[PlayerSeed, ...]


SQUAD_START_DATE = date(2026, 6, 2)
SQUAD_END_DATE = date(2026, 7, 19)
FINAL_DATE = date(2026, 7, 19)
FINAL_VENUE = "New York New Jersey Stadium"


SPAIN = TeamSeed(
    name="Spain",
    country="Spain",
    manager="Luis de la Fuente",
    players=(
        PlayerSeed("Unai Simón", "GK"),
        PlayerSeed("David Raya", "GK"),
        PlayerSeed("Joan García", "GK"),
        PlayerSeed("Pedro Porro", "DF"),
        PlayerSeed("Marcos Llorente", "DF"),
        PlayerSeed("Aymeric Laporte", "DF"),
        PlayerSeed("Pau Cubarsí", "DF"),
        PlayerSeed("Marc Pubill", "DF"),
        PlayerSeed("Eric García", "DF"),
        PlayerSeed("Marc Cucurella", "DF"),
        PlayerSeed("Alejandro Grimaldo", "DF"),
        PlayerSeed("Rodri", "MF"),
        PlayerSeed("Martín Zubimendi", "MF"),
        PlayerSeed("Pedri", "MF"),
        PlayerSeed("Fabián Ruiz", "MF"),
        PlayerSeed("Mikel Merino", "MF"),
        PlayerSeed("Gavi", "MF"),
        PlayerSeed("Álex Baena", "MF"),
        PlayerSeed("Mikel Oyarzabal", "FW"),
        PlayerSeed("Lamine Yamal", "FW"),
        PlayerSeed("Ferran Torres", "FW"),
        PlayerSeed("Borja Iglesias", "FW"),
        PlayerSeed("Dani Olmo", "FW"),
        PlayerSeed("Víctor Muñoz", "FW"),
        PlayerSeed("Nico Williams", "FW"),
        PlayerSeed("Yeremy Pino", "FW"),
    ),
)


ARGENTINA = TeamSeed(
    name="Argentina",
    country="Argentina",
    manager="Lionel Scaloni",
    players=(
        PlayerSeed("Emiliano Martínez", "GK"),
        PlayerSeed("Gerónimo Rulli", "GK"),
        PlayerSeed("Juan Musso", "GK"),
        PlayerSeed("Nahuel Molina", "DF"),
        PlayerSeed("Gonzalo Montiel", "DF"),
        PlayerSeed("Cristian Romero", "DF"),
        PlayerSeed("Marcos Senesi", "DF"),
        PlayerSeed("Nicolás Otamendi", "DF"),
        PlayerSeed("Lisandro Martínez", "DF"),
        PlayerSeed("Nicolás Tagliafico", "DF"),
        PlayerSeed("Facundo Medina", "DF"),
        PlayerSeed("Leandro Paredes", "MF"),
        PlayerSeed("Alexis Mac Allister", "MF"),
        PlayerSeed("Rodrigo De Paul", "MF"),
        PlayerSeed("Giovani Lo Celso", "MF"),
        PlayerSeed("Exequiel Palacios", "MF"),
        PlayerSeed("Enzo Fernández", "MF"),
        PlayerSeed("Valentín Barco", "MF"),
        PlayerSeed("Lionel Messi", "FW"),
        PlayerSeed("Julián Álvarez", "FW"),
        PlayerSeed("Lautaro Martínez", "FW"),
        PlayerSeed("Thiago Almada", "FW"),
        PlayerSeed("Nico Paz", "FW"),
        PlayerSeed("Nicolás González", "FW"),
        PlayerSeed("Giuliano Simeone", "FW"),
        PlayerSeed("José Manuel López", "FW"),
    ),
)

FINALISTS = (SPAIN, ARGENTINA)
