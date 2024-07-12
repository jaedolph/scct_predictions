"""Functions for getting data from SCCT."""

import os
import logging
from dataclasses import dataclass
from pathlib import Path
import socket
from contextlib import closing

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
    league: str
    winning_score: int = -1
    draw_possible: bool = False
    draw_score: int = -1

    def __repr__(self) -> str:
        """String representation of the MatchDetails."""
        return (
            f'MatchDetails(team1="{self.team1}",team2="{self.team2}",'
            f"bestof={self.bestof},score1={self.score1},score2={self.score2},"
            f"draw_possible={self.draw_possible},winning_score={self.winning_score},"
            f"league={self.league})"
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
        if not isinstance(self.league, str):
            raise ValueError("Bad value for league")

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
    profile = get_active_profile()

    match_details = None
    try:
        LOG.debug("getting scct match details")

        bestof = int(profile.get_casting_data("bestof.txt")[2:])

        match_details = MatchDetails(
            profile.get_casting_data("team1.txt"),
            profile.get_casting_data("team2.txt"),
            bestof,
            int(profile.get_casting_data("score1.txt")),
            int(profile.get_casting_data("score2.txt")),
            profile.get_casting_data("league.txt"),
        )

    except ValueError as exp:
        raise SCCTError(f"Could not get data from SCCT: {exp}") from exp

    if match_details is None:
        raise SCCTError("Could not parse match details from SCCT")

    return match_details


@dataclass
class Profile:
    """Dataclass for storing profile details."""

    profile_id: str
    port: int

    def __repr__(self) -> str:
        """String representation of the Profile."""
        return f'Profile(profile_id="{self.profile_id}",port="{self.port}")'

    def __init__(self, profile_id: str) -> None:
        """Initialise the Profile object.

        :param profile_id: hex id of the profile
        :raises ValueError: if the profile is not a valid hex number
        """
        self.profile_id = profile_id
        try:
            self.port = int(self.profile_id, 16)
            LOG.debug("converted profile hex number to port number %s", self.port)
        except ValueError as exp:
            raise ValueError(f"could not get port info from profile: {self.profile_id}") from exp

    def is_active(self) -> bool:
        """Checks if the profile is active by checking its websocket port is open.

        :return: True if the profile is active, False if not active
        """

        LOG.debug("checking if port is open for profile %s", self.profile_id)
        LOG.debug("testing if port %s is open", self.port)
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(SCCT_PORT_CHECK_TIMEOUT)
            connect_result = sock.connect_ex(("127.0.0.1", self.port))
            LOG.debug("connect result for port %s is %s", self.port, connect_result)
            if connect_result == 0:
                LOG.debug("port %s is open", self.port)
                return True

        LOG.debug("port %s is closed", self.port)
        return False

    def get_casting_data(self, filename: str) -> str:
        """Gets data from a specific "casting_data" file.

        :param filename: file to get data from e.g. league.txt
        :return: contents of the file
        :raises SCCTError: if the file is not found
        """

        data_file_path = os.path.normpath(
            f"{SCCT_PROFILES_DIR}/{self.profile_id}/casting_data/{filename}"
        )
        try:
            with open(data_file_path, "r+", encoding="utf-8") as data_file:
                return str(data_file.read())
        except FileNotFoundError as exp:
            raise SCCTError(f"Could not get data from file {data_file_path}") from exp


def get_active_profile() -> Profile:
    """Attempts to find the currently active SCCT profile.

    :return: currently active profile
    :raises SCCTError: if the currently active profile can't be detected
    """

    LOG.debug("checking scct profiles directories")
    try:
        profile_ids = os.listdir(SCCT_PROFILES_DIR)
    except FileNotFoundError as exp:
        raise SCCTError(f"could not get profile directories from {SCCT_PROFILES_DIR}") from exp
    LOG.debug("profile directories: %s", profile_ids)

    for profile_id in profile_ids:
        try:
            profile = Profile(profile_id)
        except ValueError as exp:
            LOG.warning("invalid profile %s: %s", profile_id, exp)
            continue

        LOG.debug("found profile: %s", profile)
        if profile.is_active():
            return profile

    raise SCCTError("could not find any active SCCT profile")
