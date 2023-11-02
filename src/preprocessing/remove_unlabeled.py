import pandas as pd

from ..logger.logger import logger
from ..preprocessing.pp import PP, PPException


class RemoveUnlabeled(PP):
    """Preprocessing step that removes the NaN and unlabeled data

    After adding the "awake" column with AddStateLabels, this will only keep the labeled data
    by dropping all the rows where "awake" is 3 (no more event data) and optionally 2 (don't make a prediction).
    If the "window" column in present, only drop the windows where all the "awake" values are 3 or 2.
    """

    def __init__(self, remove_only_full_windows: bool, keep_nan: bool, **kwargs: dict) -> None:
        """Initialize the RemoveUnlabeled class

        :param remove_only_full_windows: Only applies when windowing is used.
            If True, remove all windows that contain unlabeled data.
            If False, only remove the fully unlabeled windows.
        :param keep_nan: If false, remove the NaN data too. If True, keep the NaN data.
        """
        super().__init__(**kwargs | {"kind": "remove_unlabeled"})
        self.remove_only_full_windows = remove_only_full_windows
        self.keep_nan = keep_nan

    def __repr__(self) -> str:
        """Return a string representation of a RemoveUnlabeled object"""
        return f"{self.__class__.__name__}(remove_only_full_windows={self.remove_only_full_windows}, keep_nan={self.keep_nan})"

    def preprocess(self, data: pd.DataFrame) -> pd.DataFrame:
        """Removes all the data points where there is no labeled data

        :param data: The labeled dataframe to remove the unlabeled data from
        :return: The dataframe without the unlabeled data
        :raises PPException: If AddStateLabels wasn't used before
        """
        # TODO Do this check with the config checker instead #190
        if "awake" not in data.columns:
            logger.critical("No awake column. Did you run AddStateLabels before?")
            raise PPException("No awake column. Did you run AddStateLabels before?")

        if "window" in data.columns:
            logger.info("------ Removing NaN data with windowing")
            if self.remove_only_full_windows:
                data = data.groupby(["window"]).filter(lambda x: not (x['awake'] == 3).all()).reset_index(drop=True)
            else:
                data = data.groupby(["window"]).filter(lambda x: (x['awake'] != 3).any()).reset_index(drop=True)

            if not self.keep_nan:
                if self.remove_only_full_windows:
                    data = data.groupby(["window"]).filter(lambda x: not (x['awake'] == 2).all()).reset_index(drop=True)
                else:
                    data = data.groupby(["window"]).filter(lambda x: (x['awake'] != 2).any()).reset_index(drop=True)
            return data

        logger.info("------ Removing NaN data without windowing")
        data = data[(data["awake"] != 3)].reset_index(drop=True)
        if not self.keep_nan:
            data = data[(data["awake"] != 2)].reset_index(drop=True)

        return data
