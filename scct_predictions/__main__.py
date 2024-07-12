"""Main program."""

import logging
import asyncio
import uuid
import webbrowser
import argparse

from flask import Flask, make_response, redirect, render_template, request, abort
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from twitchAPI.helper import first
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.object.api import Prediction, TwitchUser
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, PredictionStatus, TwitchAPIException
from werkzeug.wrappers import Response
from wtforms import IntegerField, PasswordField, StringField, validators

from scct_predictions import scct
from scct_predictions.config import PredictionsConfig, PredictionsConfigError

CONFIG_FILE = "scct_predictions.ini"
TARGET_SCOPE = [AuthScope.CHANNEL_READ_PREDICTIONS, AuthScope.CHANNEL_MANAGE_PREDICTIONS]
APP_PORT = 5123
app = Flask(__name__)
csrf = CSRFProtect(app)
twitch: Twitch
auth: UserAuthenticator
config: PredictionsConfig

LOG = logging.getLogger(__name__)


class ConfigForm(FlaskForm):  # type: ignore
    """Form for configuring the program."""

    broadcaster_name = StringField("Channel Name (e.g. jaedolph)", [validators.DataRequired()])
    client_id = StringField("Client ID", [validators.DataRequired()])
    client_secret = PasswordField(
        "Client Secret",
        [
            validators.DataRequired(),
        ],
    )
    prediction_window = IntegerField(
        "Prediction Window (seconds)",
        [
            validators.DataRequired(),
            validators.number_range(1, 999),
        ],
        default=120,
    )


@app.errorhandler(500)
def internal_error(error: str) -> str:
    """Ensure 500 error messages also get logged.

    :param error: error message
    """

    LOG.error(error)
    return str(error)


@app.route("/predictions/create", methods=["GET"])  # type: ignore
async def predictions_create() -> Response:
    """Creates a prediction based on the current match in SCCT."""
    try:
        match = scct.get_match_details()
    except scct.SCCTError as exp:
        return abort(500, f"Failed to create prediction: {exp}")

    prediction_title = f"{match.league} (BO{match.bestof})"
    draw_possible = (match.bestof % 2) == 0

    prediction_options = []

    prediction_options.append(match.team1)
    if draw_possible:
        prediction_options.append(f"{match.draw_score} - {match.draw_score}")
    prediction_options.append(match.team2)

    try:
        broadcaster = await first(twitch.get_users(logins=[config.broadcaster_name]))
        assert isinstance(broadcaster, TwitchUser)
        await twitch.create_prediction(
            broadcaster.id,
            prediction_title,
            prediction_options,
            config.prediction_window,
        )
    except TwitchAPIException as exp:
        return abort(500, f"Failed to create prediction {exp}")
    LOG.info("Created prediction - %s", prediction_title)
    return make_response(f"Created prediction - {prediction_title}")


@app.route("/predictions/lock", methods=["GET"])  # type: ignore
async def predictions_lock() -> Response:
    """Locks the current prediction."""
    try:
        broadcaster = await first(twitch.get_users(logins=[config.broadcaster_name]))
        assert isinstance(broadcaster, TwitchUser)

        prediction = await first(twitch.get_predictions(broadcaster.id, first=1))
        assert isinstance(prediction, Prediction)

        await twitch.end_prediction(broadcaster.id, prediction.id, PredictionStatus.LOCKED)
    except TwitchAPIException as exp:
        return abort(500, f"Failed to lock prediction {exp}")
    LOG.info("Locked prediction")
    return make_response("Locked prediction")


@app.route("/predictions/cancel", methods=["GET"])  # type: ignore
async def predictions_cancel() -> Response:
    """Cancels the current prediction."""
    try:
        broadcaster = await first(twitch.get_users(logins=[config.broadcaster_name]))
        assert isinstance(broadcaster, TwitchUser)

        prediction = await first(twitch.get_predictions(broadcaster.id, first=1))
        assert isinstance(prediction, Prediction)

        await twitch.end_prediction(broadcaster.id, prediction.id, PredictionStatus.CANCELED)
    except TwitchAPIException as exp:
        return abort(500, f"Failed to cancel prediction {exp}")
    LOG.info("Cancelled prediction")
    return make_response("Cancelled prediction")


@app.route("/predictions/payout", methods=["GET"])  # type: ignore
async def predictions_payout() -> Response:
    """Pays out the current prediction if the match is complete in SCCT."""
    try:
        match = scct.get_match_details()
    except scct.SCCTError as exp:
        abort(500, f"Failed to payout prediction: {exp}")

    winning_outcome = ""

    if match.score1 >= match.winning_score:
        winning_outcome = match.team1
    elif match.score2 >= match.winning_score:
        winning_outcome = match.team2
    elif (
        match.score1 == match.score2
        and (match.score1 + match.score2 == match.bestof)
        and match.draw_possible
    ):
        winning_outcome = f"{match.draw_score} - {match.draw_score}"
    else:
        return abort(
            500,
            "Could not determine outcome, match may not be finished: "
            f"{match.team1} {match.score2} - {match.team2} {match.score2}",
        )

    try:
        broadcaster = await first(twitch.get_users(logins=[config.broadcaster_name]))
        assert isinstance(broadcaster, TwitchUser)

        prediction = await first(twitch.get_predictions(broadcaster.id, first=1))
        assert isinstance(prediction, Prediction)

        winning_outcome_id = None
        for outcome in prediction.outcomes:
            if outcome.title == winning_outcome:
                winning_outcome_id = outcome.id
                break
        if not winning_outcome_id:
            return abort(500, "could not find winning outcome")

        await twitch.end_prediction(
            broadcaster.id, prediction.id, PredictionStatus.RESOLVED, winning_outcome_id
        )
    except TwitchAPIException as exp:
        return abort(500, f"Failed to payout prediction {exp}")

    LOG.info("Paid out prediction, result: %s", winning_outcome)
    return make_response(f"Paid out prediction, result: {winning_outcome}")


@app.route("/configure", methods=["GET", "POST"])  # type: ignore
async def configure() -> Response:
    """Serves the configuration form for the program."""

    global twitch, auth  # pylint: disable=global-statement
    form = ConfigForm(request.form)
    if request.method == "POST" and form.validate():
        assert form.client_secret.data is not None
        assert form.client_id.data is not None
        assert form.broadcaster_name.data is not None
        assert form.prediction_window.data is not None

        config.broadcaster_name = form.broadcaster_name.data.lower()
        config.client_id = form.client_id.data
        config.client_secret = form.client_secret.data
        config.prediction_window = form.prediction_window.data
        twitch = await Twitch(config.client_id, config.client_secret)
        auth = UserAuthenticator(
            twitch,
            TARGET_SCOPE,
            force_verify=False,
            url=f"http://localhost:{APP_PORT}/configure/confirm",
        )
        return redirect(auth.return_auth_url())  # type: ignore

    return make_response(render_template("config.html", form=form, app_port=APP_PORT))


@app.route("/configure/confirm", methods=["GET"])  # type: ignore
async def login_confirm() -> Response:
    """Parse details from Twitch Oauth redirect and finish configuration."""

    state = request.args.get("state")
    LOG.debug("got state: %s", state)
    if state != auth.state:
        return abort(400, "bad state")
    code = request.args.get("code")
    if code is None:
        return abort(400, "missing code")
    try:
        config.auth_token, config.refresh_token = await auth.authenticate(user_token=code)
        await twitch.set_user_authentication(config.auth_token, TARGET_SCOPE, config.refresh_token)

        config.validate_twitch_section()
        config.write_config()
    except TwitchAPIException:
        return abort(400, "failed to generate auth token")

    return make_response(render_template("config_success.html", app_port=APP_PORT))


async def twitch_setup() -> None:
    """Setup twitch config on program start."""

    global twitch, config  # pylint: disable=global-statement
    config = PredictionsConfig(CONFIG_FILE)
    try:
        config.load_config()
        twitch = await Twitch(config.client_id, config.client_secret)
        await twitch.set_user_authentication(config.auth_token, TARGET_SCOPE, config.refresh_token)
    except PredictionsConfigError as exp:
        logging.error("Bad config: %s", exp)
        config = PredictionsConfig(CONFIG_FILE)
        config.new_config()

        logging.debug("opening configuration form in browser")
        browser = webbrowser.get()
        browser.open(f"http://localhost:{APP_PORT}/configure")


def main() -> None:
    """Main entrypoint."""
    parser = argparse.ArgumentParser(
        prog="scct_predictions",
        description="Creates and pays out Twitch predictions based on data from SCCT.",
    )
    parser.add_argument("--debug", action="store_true", help="turn on debug logging")
    parser.add_argument("--log-file", help="path to log file")
    args = parser.parse_args()

    # configure logging
    log_level = logging.INFO
    log_handlers: list[logging.Handler] = [logging.StreamHandler()]
    if args.debug:
        LOG.info("setting log level to DEBUG")
        log_level = logging.DEBUG
        LOG.debug("test logging")

    if args.log_file:
        log_handlers.append(logging.FileHandler(args.log_file))

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        level=log_level,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=log_handlers,
    )
    logging.debug("generating secret key")
    app.secret_key = uuid.uuid4().hex

    asyncio.run(twitch_setup())
    csrf.init_app(app)
    app.run(port=APP_PORT)


if __name__ == "__main__":
    main()
