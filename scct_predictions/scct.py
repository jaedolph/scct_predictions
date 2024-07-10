"""Functions for getting data from SCCT."""

import os
import json
import logging
from dataclasses import dataclass
from pathlib import Path
import socket
from contextlib import closing

from websocket import WebSocketTimeoutException, create_connection

SCCT_SCORE_WEBSOCKET = "ws://localhost:{}/score"
LOG = logging.getLogger(__name__)

HOMEDIR = str(Path.home())
SCCT_PROFILES_DIR = os.path.normpath(
    f"{HOMEDIR}/AppData/Local/team pheeniX/StarCraft-Casting-Tool/profiles"
)
SCCT_PORT_CHECK_TIMEOUT = 0.2


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

    def __repr__(self) -> str:
        """String representation of the MatchDetails."""
        return (
            f'MatchDetails(team1="{self.team1}",team2="{self.team2}",'
            f"bestof={self.bestof},score1={self.score1},score2={self.score2},"
            f"draw_possible={self.draw_possible},winning_score={self.winning_score})"
        )

    def __post_init__(self) -> None:
        """Ensures data is valid and calculates win conditions."""
        LOG.debug("parsing match details")
        if not isinstance(self.team1, str):
            raise ValueError("Bad value for team1")
        if not isinstance(self.team2, str):
            raise ValueError("Bad value for team2")
        if not isinstance(self.bestof, int):
            raise ValueError("Bad value for bestof")
        if not isinstance(self.score1, int):
            raise ValueError("Bad value for score1")
        if not isinstance(self.score2, int):
            raise ValueError("Bad value for score2")

        self.draw_possible = (self.bestof % 2) == 0
        self.winning_score = int(self.bestof / 2) + 1
        if self.draw_possible:
            self.draw_score = int(self.bestof / 2)
        LOG.info("finished parsing match details: %s", str(self))


def get_match_details() -> MatchDetails:
    """Gets the current match details from SCCT.

    :return: current match details from SCCT
    :raises SCCTError: when there is an error getting the match details
    """
    port = get_websocket_port()
    match_details = None
    try:
        LOG.debug("creating connection to scct websocket")
        ws = create_connection(SCCT_SCORE_WEBSOCKET.format(port), timeout=1)
        for _ in range(0, 3):
            response = ws.recv()
            LOG.debug("received response from websocket: %s", response)
            response_json = json.loads(response)
            if response_json["event"] == "ALL_DATA":
                LOG.debug("found match details")
                match_details = MatchDetails(
                    response_json["data"]["team1"],
                    response_json["data"]["team2"],
                    response_json["data"]["bestof"],
                    response_json["data"]["score1"],
                    response_json["data"]["score2"],
                )
                break
    except (ConnectionRefusedError, TimeoutError) as exp:
        raise SCCTError("Could not connect to SCCT") from exp
    except WebSocketTimeoutException as exp:
        raise SCCTError("Connection to SCCT timed out") from exp
    except ValueError as exp:
        raise SCCTError(f"Could not get data from SCCT: {exp}") from exp

    if match_details is None:
        raise SCCTError("Could not parse match details from SCCT")

    return match_details


def get_websocket_port() -> int:
    """Attempts to find an open websocket port to use to get data from SCCT.

    :return: websocket port number
    :raises SCCTError: if there is an error finding the port
    """

    LOG.debug("checking scct profiles directories")
    try:
        profiles = os.listdir(SCCT_PROFILES_DIR)
    except FileNotFoundError as exp:
        raise SCCTError(f"could not get profile directories from {SCCT_PROFILES_DIR}") from exp
    LOG.debug("profile directories: %s", profiles)

    for profile in profiles:
        LOG.debug("checking if port is open for profile %s", profile)
        try:
            port_num = int(profile, 16)
            LOG.debug("converted profile hex number to port number %s", port_num)
        except ValueError:
            LOG.warning("could not get port info from profile: %s", profile)
            continue

        LOG.debug("testing if port %s is open", port_num)
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(SCCT_PORT_CHECK_TIMEOUT)
            connect_result = sock.connect_ex(("127.0.0.1", port_num))
            LOG.debug("connect result for port %s is %s", port_num, connect_result)
            if connect_result == 0:
                LOG.debug("port %s is open", port_num)
                return port_num
            LOG.debug("port %s is closed", port_num)

    raise SCCTError("could not find any valid SCCT websocket ports")
