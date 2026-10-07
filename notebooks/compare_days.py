"""Replay the demo contrast from the command line."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.presets import preset
from app.simulation.engine import run_simulation


def main() -> None:
    for key in ("baseline", "universal", "extra_social_worker"):
        scenario = preset(key)
        metrics = run_simulation(scenario, trace=False)["metrics"]
        print(
            f"{scenario.name:32} need {metrics['families_with_need']:2}  "
            f"identified {metrics['identified']:2}  missed {metrics['missed']:2}  "
            f"supported {metrics['supported']:2}  psych wait {metrics['mean_psych_wait']:5.1f}  "
            f"SW util {metrics['utilization']['social_work']:.0%}  "
            f"left {metrics['left_before_psych']}"
        )


if __name__ == "__main__":
    main()
