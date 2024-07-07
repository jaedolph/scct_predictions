"""PredictionsConfig class used for storing/validating configuration."""

import configparser
import os


class PredictionsConfigError(Exception):
    """Custom exception thrown when the configuration is invalid."""


# pylint: disable=too-many-public-methods
class PredictionsConfig:
    """Stores and manages config for the application.

    :param config_file_path: path to the config file to read/write
    """

    def __init__(self, config_file_path: str) -> None:
        """Initialize the PredictionsConfig."""
        self.config_file_path = config_file_path
        self.config = configparser.ConfigParser()

    def new_config(self) -> None:
        """Creates sections so new config can be created."""
        self.config.add_section("TWITCH")

    def load_config(self) -> None:
        """Creates sections so new config can be created."""
        if not os.path.isfile(self.config_file_path):
            raise PredictionsConfigError(f'could not open config file "{self.config_file_path}"')

        self.config.read(self.config_file_path)
        self.validate_config()

    def validate_twitch_section(self) -> None:
        """Validates the [TWITCH] section of the config."""

        try:
            assert self.config.has_section("TWITCH")
            assert isinstance(self.client_id, str)
            assert isinstance(self.client_secret, str)
            assert isinstance(self.broadcaster_name, str)
            assert isinstance(self.auth_token, str)
            assert isinstance(self.refresh_token, str)
            assert isinstance(self.prediction_window, int)
        except (configparser.Error, AssertionError, ValueError, KeyError) as exp:
            raise PredictionsConfigError(exp) from exp

    def validate_config(self) -> None:
        """Validates that the current config."""
        self.validate_twitch_section()

    def write_config(self) -> None:
        """Writes current config to file."""
        self.validate_config()
        with open(self.config_file_path, "w", encoding="utf-8") as config_file:
            self.config.write(config_file)

    # pylint: disable=missing-function-docstring
    @property
    def auth_token(self) -> str:
        return self.config["TWITCH"]["AUTH_TOKEN"]

    @auth_token.setter
    def auth_token(self, value: str) -> None:
        self.config["TWITCH"]["AUTH_TOKEN"] = value

    @property
    def refresh_token(self) -> str:
        return self.config["TWITCH"]["REFRESH_TOKEN"]

    @refresh_token.setter
    def refresh_token(self, value: str) -> None:
        self.config["TWITCH"]["REFRESH_TOKEN"] = value

    @property
    def client_id(self) -> str:
        return self.config["TWITCH"]["CLIENT_ID"]

    @client_id.setter
    def client_id(self, value: str) -> None:
        self.config["TWITCH"]["CLIENT_ID"] = value

    @property
    def client_secret(self) -> str:
        return self.config["TWITCH"]["CLIENT_SECRET"]

    @client_secret.setter
    def client_secret(self, value: str) -> None:
        self.config["TWITCH"]["CLIENT_SECRET"] = value

    @property
    def broadcaster_name(self) -> str:
        return self.config["TWITCH"]["BROADCASTER_NAME"]

    @broadcaster_name.setter
    def broadcaster_name(self, value: str) -> None:
        self.config["TWITCH"]["BROADCASTER_NAME"] = value

    @property
    def prediction_window(self) -> int:
        return self.config.getint("TWITCH", "PREDICTION_WINDOW")

    @prediction_window.setter
    def prediction_window(self, value: int) -> None:
        self.config["TWITCH"]["PREDICTION_WINDOW"] = str(value)

    # pylint: disable=
