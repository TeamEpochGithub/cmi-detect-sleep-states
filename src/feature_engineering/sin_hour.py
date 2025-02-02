import gc
from dataclasses import dataclass

import numpy as np
from tqdm import tqdm

from .feature_engineering import FE
from ..logger.logger import logger


@dataclass
class SinHour(FE):
    """

    # This step will take the hour from the column with the datetime
    and map the hours between 0-2*pi and take the sin of it
    Unless this is done the hour features spectrogram will have harmonics
    """

    def feature_engineering(self, data: dict) -> dict:
        """Process the data. This method should be overritten by the child class.

        :param data: the data to process
        :return: the processed data
        """
        # assert that the data has a timestamp column
        assert "timestamp" in data[0].columns, "dataframe has no timestamp column"

        # get the hour from the datetime column
        for sid in tqdm(data.keys()):
            hour = data[sid]['timestamp'].dt.hour

            # map the hour to a value between 0-2*pi
            hour = hour.map(lambda x: x / 24 * 2 * np.pi)
            sin_hour = np.sin(hour)
            data[sid]['f_sin_hour'] = sin_hour
            logger.debug('------ Added sin hour feature to series')
            gc.collect()
        return data
