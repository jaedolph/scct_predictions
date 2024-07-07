"""Functions for getting data from SCCT."""

import json
from dataclasses import dataclass

from websocket import WebSocketTimeoutException, create_connection

SCCT_SCORE_WEBSOCKET = "ws://localhost:62345/score"


class SCCTError(Exception):
    """Custom exception thrown when there is an issue getting data form SCCT."""


@dataclass
class MatchDetails:
    """Dataclass for storing match details."""

    team1: str
    team2: str
    bestof: int
    score1: int
    score2: int
    winning_score: int = -1
    draw_possible: bool = False
    draw_score: int = -1

    def __post_init__(self) -> None:
        """Ensures data is valid and calculates win conditions."""
        if not isinstance(self.team1, str):
            raise ValueError("Bad value for team1")
        if not isinstance(self.team2, str):
            raise ValueError("Bad value for team2")
        if not isinstance(self.bestof, int):
            raise ValueError("Bad value for bestof")
        if not isinstance(self.score1, int):
            raise ValueError("Bad value for score1")
        if not isinstance(self.score1, int):
            raise ValueError("Bad value for score2")

        self.draw_possible = (self.bestof % 2) == 0
        self.winning_score = int(self.bestof / 2) + 1
        if self.draw_possible:
            self.draw_score = int(self.bestof / 2)


def get_match_details() -> MatchDetails:
    """Gets the current match details from SCCT.

    :return: current match details from SCCT
    :raises SCCTError: when there is an error getting the match details
    """

    match_details = None
    try:
        ws = create_connection(SCCT_SCORE_WEBSOCKET, timeout=5)
        for _ in range(0, 3):
            response = ws.recv()
            response_json = json.loads(response)
            if response_json["event"] == "ALL_DATA":
                match_details = MatchDetails(
                    response_json["data"]["team1"],
                    response_json["data"]["team2"],
                    response_json["data"]["bestof"],
                    response_json["data"]["score1"],
                    response_json["data"]["score2"],
                )
                break
    except ConnectionRefusedError as exp:
        raise SCCTError("Could not connect to SCCT") from exp
    except WebSocketTimeoutException as exp:
        raise SCCTError("Connection to SCCT timed out") from exp
    except ValueError as exp:
        raise SCCTError(f"Could not get data from SCCT: {exp}") from exp

    assert match_details is not None

    return match_details
