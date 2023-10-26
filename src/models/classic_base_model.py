from typing import Any

import numpy as np
import pandas as pd
from numpy import ndarray, dtype
from tqdm import tqdm

from ..logger.logger import logger
from ..models.model import Model
from ..util.state_to_event import find_events


class ClassicBaseModel(Model):
    """
    This is a sample model file. You can use this as a template for your own models.
    The model file should contain a class that inherits from the Model class.
    """

    def __init__(self, config: dict, name: str, pred_with_cpu: bool) -> None:
        """
        Init function of the example model
        :param config: configuration to set up the model
        :param name: name of the model
        :param pred_with_cpu: (UNUSED) whether to make predictions using the CPU or GPU
        """
        super().__init__(config, name, pred_with_cpu)
        self.model_type = "classic-base-model"
        self.load_config(config)

    def load_config(self, config: dict) -> None:
        """
        Load config function for the model.
        :param config: configuration to set up the model
        """

        # Get default_config
        default_config = self.get_default_config()

        config["median_window"] = config.get("median_window", default_config["median_window"])
        config["threshold"] = config.get("threshold", default_config["threshold"])
        config["use_nan_similarity"] = config.get("use_nan_similarity", default_config["use_nan_similarity"])
        self.config = config

    def get_default_config(self) -> dict:
        """
        Get default config function for the model.
        :return: default config
        """
        return {"median_window": 100, "threshold": .1, "use_nan_similarity": True}

    def pred(self, X_pred: np.ndarray) -> ndarray[Any, dtype[Any]]:
        """
        Prediction function for the model.
        :param X_pred: unlabeled data for a single day window as pandas dataframe
        :return: two timestamps, or NaN if no sleep was detected
        """

        logger.info(f"--- Predicting results with model {self.name}")
        predictions = []
        # Get the data from the data tuple
        for window in tqdm(X_pred, desc="Converting predictions to events", unit="window"):
            state_pred = self.predict_state_labels(window)

            if self.config["use_nan_similarity"]:
                state_pred[window[:, 2] == 0] = 2  # Assuming feature 2 is similarity nan
            events = find_events(state_pred)
            predictions.append(events)

        return np.array(predictions)

    def predict_state_labels(self, data: np.ndarray) -> np.ndarray:
        anglez = pd.Series(data[:, 1])  # Assuming feature 1 is anglez
        slope = abs(anglez.diff()).clip(upper=10)
        movement = pd.Series(slope).rolling(window=100, center=True).median()
        pred = (movement > .1)
        return pred.to_numpy(dtype='float32')
