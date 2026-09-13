"""Toggle forecast experiments. Default flags = production baseline."""

from __future__ import annotations

FLAGS = {
    "prepay": False,
    "prepay_scale": 1.0,
    "var_max": False,
    "daily_until_payday": True,
    "lump_daily_to_payday": False,
}


def reset(**overrides) -> None:
    FLAGS.update(
        {
            "prepay": False,
            "prepay_scale": 1.0,
            "var_max": False,
            "daily_until_payday": True,
            "lump_daily_to_payday": False,
        }
    )
    FLAGS.update(overrides)
