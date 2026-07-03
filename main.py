import argparse
import logging

from utm.log_config import setup_logging
from tournaments.run_round_robin import run_tournament


def _build_utm_tft():
    from strategies.utm_tft import UTMTFT

    return UTMTFT()


def _build_tft():
    import axelrod as axl

    return axl.TitForTat()


def _build_wsls():
    import axelrod as axl

    return axl.WinStayLoseShift()


def _build_defector():
    import axelrod as axl

    return axl.Defector()


def _build_cooperator():
    import axelrod as axl

    return axl.Cooperator()


def _build_random():
    import axelrod as axl

    return axl.Random(p=0.5)


APPROVED_PLAYER_BUILDERS = {
    "utm_tft": _build_utm_tft,
    "tft": _build_tft,
    "wsls": _build_wsls,
    "alld": _build_defector,
    "allc": _build_cooperator,
    "random": _build_random,
}


def approved_player_ids() -> tuple[str, ...]:
    return tuple(APPROVED_PLAYER_BUILDERS)


def build_approved_player(name: str):
    try:
        return APPROVED_PLAYER_BUILDERS[name]()
    except KeyError as exc:
        allowed = ", ".join(approved_player_ids())
        raise ValueError(
            f"Unsupported player '{name}'. Choose one of: {allowed}."
        ) from exc


if __name__ == "__main__":
    # ----------------------------------------
    # 1) Configure logging before anything else
    # ----------------------------------------
    setup_logging(level_console="INFO")
    logger = logging.getLogger(__name__)
    logger.info("Starting tournament runner")

    # ----------------------------------------
    # 2) Parse command-line arguments
    # ----------------------------------------
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=200)
    p.add_argument("--reps",   type=int, default=30)
    p.add_argument(
        "--players",
        nargs="*",
        default=["utm_tft", "tft", "wsls", "alld", "allc", "random"],
        help="List of approved player identifiers",
    )
    args = p.parse_args()
    logger.info(
        "Parsed args: rounds=%d, reps=%d, players=%s",
        args.rounds,
        args.reps,
        args.players,
    )

    # ----------------------------------------
    # 3) Instantiate approved players
    # ----------------------------------------
    player_objs = []
    for name in args.players:
        logger.info("Loading player '%s'", name)
        try:
            player = build_approved_player(name)
        except ValueError as exc:
            logger.error("Rejected unsupported player '%s'", name)
            p.error(str(exc))
        player_objs.append(player)
        logger.info("→ Instantiated approved player %s: %s", name, player)

    # ----------------------------------------
    # 4) Run the tournament
    # ----------------------------------------
    logger.info(
        "Running round-robin tournament with %d players, %d turns, %d repetitions",
        len(player_objs),
        args.rounds,
        args.reps,
    )
    run_tournament(player_objs, turns=args.rounds, repetitions=args.reps)
    logger.info("Tournament completed")
