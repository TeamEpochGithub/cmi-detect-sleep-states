from dataclasses import dataclass

import pandas as pd

from .feature_engineering import FE, FEException
from ..logger.logger import logger

_TIME_FEATURES: list[str] = ["year", "month", "day", "hour", "minute", "second", "microsecond"]


@dataclass
class Time(FE):
    """Add time features to the data

    The following time-related features can be added: "year", "month", "day", "hour", "minute", "second", "microsecond".
    # TODO Add "weekday" and "week"

    :param time_features: the time features to add
    """
    time_features: list[str]

    def __post_init__(self) -> None:
        """Check if the time features are supported"""
        if any(time_feature not in _TIME_FEATURES for time_feature in self.time_features):
            logger.critical(f"Unknown time features: {self.time_features}")
            raise FEException(f"Unknown time features: {self.time_features}")

    def feature_engineering(self, data: dict) -> dict:
        """Add the selected time columns.

        :param data: the original data
        :return: the data with the selected time data added
        """
        for time_feature in self.time_features:
            for sid in data.keys():
                data[sid][f"f_{time_feature}"] = data[sid]["timestamp"].dt.__getattribute__(time_feature)

        return data
