import argparse
import importlib
import logging

from utm.log_config import setup_logging
from tournaments.run_round_robin import run_tournament

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
        help="List of player identifiers or module paths",
    )
    args = p.parse_args()
    logger.info(
        "Parsed args: rounds=%d, reps=%d, players=%s",
        args.rounds,
        args.reps,
        args.players,
    )

    # ----------------------------------------
    # 3) Dynamically import and instantiate players
    # ----------------------------------------
    player_objs = []
    for name in args.players:
        logger.info("Loading player '%s'", name)
        if name == "utm_tft":
            from strategies.utm_tft import UTMTitForTat
            player = UTMTitForTat()
            player_objs.append(player)
            logger.info("→ Instantiated UTMTitForTat: %s", player)
        elif name in {"tft", "wsls", "alld", "allc", "random"}:
            import axelrod as axl

            mapping = {
                "tft":   axl.TitForTat,
                "wsls":  axl.WinStayLoseShift,
                "alld":  axl.Defector,
                "allc":  axl.Cooperator,
                "random": lambda: axl.Random(p=0.5),
            }
            player = mapping[name]()
            player_objs.append(player)
            logger.info("→ Instantiated Axelrod %s: %s", name, player)
        else:
            # Allow full module path, e.g. "mypackage.MyPlayer"
            try:
                modpath, clsname = name.rsplit(".", 1)
                cls = getattr(importlib.import_module(modpath), clsname)
                player = cls()
                player_objs.append(player)
                logger.info("→ Dynamically imported %s.%s: %s", modpath, clsname, player)
            except Exception as e:
                logger.error("Failed to import '%s': %s", name, e)
                raise

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
