from dataclasses import dataclass

import pandas as pd

from ..logger.logger import logger
from ..preprocessing.pp import PP, PPException


@dataclass
class RemoveUnlabeled(PP):
    """Preprocessing step that removes the NaN and unlabeled data

    After adding the "awake" column with AddStateLabels, this will only keep the labeled data
    by dropping all the rows where "awake" is 3 (no more event data) and optionally 2 (don't make a prediction).
    If the "window" column in present, only drop the windows where all the "awake" values are 3 or 2.

    :param remove_partially_unlabeled_windows: Only applies when windowing is used.
        If True, remove all windows that contain unlabeled data.
        If False, only remove the fully unlabeled windows.
    :param remove_nan: If false, remove the NaN data too. If True, keep the NaN data.
    :param remove_entire_series: If True, remove all series that contain unlabeled data. Ignores windowing.
    """
    remove_partially_unlabeled_windows: bool
    remove_nan: bool
    remove_entire_series: bool

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

        logger.info(f"------ Data shape before: {data.shape}")

        if self.remove_entire_series:
            # Remove series that have at least one 3
            data = data.groupby(["series_id"]).filter(lambda x: (x['awake'] != 3).all()).reset_index(drop=True)
            if self.remove_nan:
                # Remove series that have at least one 2
                data = data.groupby(["series_id"]).filter(lambda x: (x['awake'] != 2).all()).reset_index(drop=True)

            logger.info(f"------ Data shape after: {data.shape}")
            return data

        if "window" in data.columns:
            logger.info("------ Removing unlabeled data with windowing")
            if self.remove_partially_unlabeled_windows:
                # Remove windows that have at least one 3
                data = data.groupby(["series_id", "window"]).filter(lambda x: not (x['awake'] == 3).any()).reset_index(
                    drop=True)
            else:
                # Remove windows that are completely 3
                data = data.groupby(["series_id", "window"]).filter(lambda x: (x['awake'] != 3).any()).reset_index(
                    drop=True)

            if self.remove_nan:
                if self.remove_partially_unlabeled_windows:
                    # Remove windows that have at least one 2
                    data = data.groupby(["series_id", "window"]).filter(
                        lambda x: not (x['awake'] == 2).any()).reset_index(drop=True)
                else:
                    # Remove windows that are completely 2
                    data = data.groupby(["series_id", "window"]).filter(lambda x: (x['awake'] != 2).any()).reset_index(
                        drop=True)

            logger.info(f"------ Data shape after: {data.shape}")
            return data

        logger.info("------ Removing unlabeled data without windowing")
        data = data[(data["awake"] != 3)].reset_index(drop=True)
        if self.remove_nan:
            data = data[(data["awake"] != 2)].reset_index(drop=True)

        logger.info(f"------ Data shape after: {data.shape}")
        return data

    @staticmethod
    def reset_windows_indices(data: pd.DataFrame) -> pd.DataFrame:
        """Reset the window number after removing unlabeled data

        :param data: The dataframe to reset the window number with columns "series_id" and "window"
        """
        data["window"] = (data.groupby("series_id")["window"].rank(method="dense").sub(1).astype(int)
                          .reset_index(drop=True))
        return data
