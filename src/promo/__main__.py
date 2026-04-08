import sys

from promo.admin_cli.main import main as cli_main
from promo.presentation.app import run_server


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "serve":
        raise SystemExit(run_server(argv[1:]))
    raise SystemExit(cli_main(argv))
