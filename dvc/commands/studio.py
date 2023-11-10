import argparse
import logging
import os

from funcy import get_in

from dvc.cli.command import CmdBase
from dvc.cli.utils import append_doc_link, fix_subparsers

logger = logging.getLogger(__name__)

DEFAULT_SCOPES = "live,dvc_experiment,view_url,dql,download_model"
AVAILABLE_SCOPES = ["live", "dvc_experiment", "view_url", "dql", "download_model"]


class CmdStudioLogin(CmdBase):
    def run(self):
        from dvc_studio_client.auth import check_token_authorization

        from dvc.env import DVC_STUDIO_URL
        from dvc.repo.experiments.utils import gen_random_name
        from dvc.ui import ui
        from dvc.utils.studio import STUDIO_URL

        name = self.args.name or gen_random_name()
        hostname = self.args.hostname or os.environ.get(DVC_STUDIO_URL) or STUDIO_URL

        try:
            device_code, token_uri = self.initiate_authorization(name, hostname)
        except ValueError as e:
            ui.error_write(str(e))
            return 1

        access_token = check_token_authorization(uri=token_uri, device_code=device_code)
        if not access_token:
            ui.write(
                "failed to authenticate: This 'device_code' has expired.(expired_token)"
            )
            return 1

        self.save_config(hostname, access_token)
        ui.write(
            f"Authentication successful. The token will be "
            f"available as {name} in Studio profile."
        )
        return 0

    def initiate_authorization(self, name, hostname):
        import webbrowser

        from dvc_studio_client.auth import start_device_login

        from dvc.ui import ui

        scopes = self.args.scopes or DEFAULT_SCOPES

        response = start_device_login(
            client_name="dvc",
            base_url=hostname,
            token_name=name,
            scopes=scopes.split(","),
        )
        verification_uri = response["verification_uri"]
        user_code = response["user_code"]
        device_code = response["device_code"]
        token_uri = response["token_uri"]

        opened = False
        if not self.args.use_device_code:
            ui.write(
                f"A web browser has been opened at \n{verification_uri}.\n"
                f"Please continue the login in the web browser.\n"
                f"If no web browser is available or if the web browser fails to open,\n"
                f"use device code flow with `dvc studio login --use-device-code`."
            )
            url = f"{verification_uri}?code={user_code}"
            opened = webbrowser.open(url)

        if not opened:
            ui.write(
                f"Please open the following url in your browser.\n{verification_uri}"
            )
            ui.write(f"And enter the user code below {user_code} to authorize.")
        return device_code, token_uri

    def save_config(self, hostname, token):
        with self.config.edit("global") as conf:
            conf["studio"]["token"] = token
            conf["studio"]["url"] = hostname


class CmdStudioLogout(CmdBase):
    def run(self):
        from dvc.ui import ui

        with self.config.edit("global") as conf:
            if not get_in(conf, ["studio", "token"]):
                ui.error_write("Not logged in to Studio.")
                return 1

            del conf["studio"]["token"]

        ui.write("Logged out from Studio")
        return 0


class CmdStudioToken(CmdBase):
    def run(self):
        from dvc.ui import ui

        conf = self.config.read("global")
        token = get_in(conf, ["studio", "token"])
        if not token:
            ui.error_write("Not logged in to Studio.")
            return 1

        ui.write(token)
        return 0


def add_parser(subparsers, parent_parser):
    STUDIO_HELP = "Authenticate dvc with Iterative Studio"
    STUDIO_DESCRIPTION = (
        "Authorize dvc with Studio and set the token. When this is\n"
        "set, DVC uses this to share live experiments and notify\n"
        "Studio about pushed experiments."
    )

    studio_parser = subparsers.add_parser(
        "studio",
        parents=[parent_parser],
        description=append_doc_link(STUDIO_DESCRIPTION, "studio"),
        help=STUDIO_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    studio_subparser = studio_parser.add_subparsers(
        dest="cmd",
        help="Use `dvc studio CMD --help` to display command-specific help.",
    )
    fix_subparsers(studio_subparser)

    STUDIO_LOGIN_HELP = "Authenticate DVC with Studio host"
    STUDIO_LOGIN_DESCRIPTION = (
        "By default, this command authorize dvc with Studio with\n"
        " default scopes and a random  name as token name."
    )
    login_parser = studio_subparser.add_parser(
        "login",
        parents=[parent_parser],
        description=append_doc_link(STUDIO_LOGIN_DESCRIPTION, "studio/login"),
        help=STUDIO_LOGIN_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    login_parser.add_argument(
        "-H",
        "--hostname",
        action="store",
        default=None,
        help="The hostname of the Studio instance to authenticate with.",
    )
    login_parser.add_argument(
        "-s",
        "--scopes",
        action="store",
        default=None,
        help="The scopes for the authentication token. ",
    )

    login_parser.add_argument(
        "-n",
        "--name",
        action="store",
        default=None,
        help="The name of the authentication token. It will be used to\n"
        "identify token shown in Studio profile.",
    )

    login_parser.add_argument(
        "-d",
        "--use-device-code",
        action="store_true",
        default=False,
        help="Use authentication flow based on user code.\n"
        "You will be presented with user code to enter in browser.\n"
        "DVC will also use this if it cannot launch browser on your behalf.",
    )
    login_parser.set_defaults(func=CmdStudioLogin)

    STUDIO_LOGOUT_HELP = "Logout user from Studio"
    STUDIO_LOGOUT_DESCRIPTION = "This command helps to log out user from DVC Studio.\n"

    logout_parser = studio_subparser.add_parser(
        "logout",
        parents=[parent_parser],
        description=append_doc_link(STUDIO_LOGOUT_DESCRIPTION, "studio/logout"),
        help=STUDIO_LOGOUT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    logout_parser.set_defaults(func=CmdStudioLogout)

    STUDIO_TOKEN_HELP = (
        "View the token dvc uses to contact Studio"  # noqa: S105 # nosec B105
    )

    logout_parser = studio_subparser.add_parser(
        "token",
        parents=[parent_parser],
        description=append_doc_link(STUDIO_TOKEN_HELP, "studio/token"),
        help=STUDIO_TOKEN_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    logout_parser.set_defaults(func=CmdStudioToken)
