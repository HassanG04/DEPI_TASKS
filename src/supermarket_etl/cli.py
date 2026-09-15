from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate, clean, and analyze supermarket sales data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("assignment panda/data/SuperMarket.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    result = run_pipeline(args.input, args.output_dir)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
