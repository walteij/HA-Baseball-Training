"""Constants for the Honkbal Trainer integration."""

from typing import Final

DOMAIN: Final = "honkbal_trainer"
PLATFORMS: Final = ["calendar", "sensor", "select", "button"]
STORAGE_VERSION: Final = 2
DEFAULT_SESSION_MINUTES: Final = 90
DEFAULT_WARMUP_MINUTES: Final = 20
DEFAULT_WEEKS: Final = 8
REPEAT_GAP_DAYS: Final = 14
PROGRAM: Final = [
    ("batting", "infield"),
    ("pitching", "catching"),
    ("batting", "baserunning"),
    ("infield", "outfield", "throwing"),
    ("pitching", "catching"),
    ("batting", "situational"),
    ("infield", "catching"),
    ("batting", "pitching"),
]
THEMES: Final = [
    "batting",
    "pitching",
    "catching",
    "infield",
    "outfield",
    "throwing",
    "baserunning",
    "situational",
    "conditioning",
]
THEME_LABELS: Final = {
    "batting": "slagtraining",
    "pitching": "werpen",
    "catching": "vangen",
    "infield": "binnenveld",
    "outfield": "buitenveld",
    "throwing": "gooien",
    "baserunning": "honklopen",
    "situational": "spelsituaties",
    "conditioning": "conditie",
}
BLOCK_LABELS: Final = {
    "foundation": "Basisblok",
    "theme_1": "Thema 1",
    "theme_2": "Thema 2",
    "closing": "Afsluiting",
}
FOCUSES: Final = ["techniek", "spelplezier", "conditie", "herstel"]
DEFAULT_EQUIPMENT: Final = [
    "balls",
    "wiffle_balls",
    "gloves",
    "cones",
    "bat",
    "net",
    "resistance_bands",
]
WEEKDAYS: Final = {
    "maandag": 0,
    "dinsdag": 1,
    "woensdag": 2,
    "donderdag": 3,
    "vrijdag": 4,
    "zaterdag": 5,
    "zondag": 6,
}
