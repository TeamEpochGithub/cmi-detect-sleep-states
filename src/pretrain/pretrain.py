from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from ..scaler.scaler import Scaler


class Pretrain:
    """This class is used to prepare the data for training

    It's main functionality is to split the data into train and test sets,
    standardize the data according to the train set, split the data into features and labels,
    and convert the data to a numpy array.
    """

    def __init__(self, scaler: Scaler, test_size: float):
        """Initialize the pretrain object

        :param scaler: the scaler to use
        :param test_size: the size of the test set
        """
        self.scaler = scaler
        self.test_size = test_size

    @staticmethod
    def from_config(config: dict) -> Pretrain:
        """Create a pretrain object from the config

        :param config: the config to create the pretrain object from
        :return: the pretrain object
        """

        scaler = Scaler(**config['scaler'])
        test_size = config["test_size"]

        return Pretrain(scaler, test_size)

    def pretrain_split(self, df: pd.DataFrame) -> (np.array, np.array, np.array, np.array, np.array, np.array):
        """Prepare the data for training

        It splits the data into train and test sets, standardizes the data according to the train set,
        splits the data into features and labels, and converts the data to a numpy array.

        :param df: the dataframe to pretrain on
        :return: the train data, test data, train labels, test labels, train indices and test indices
        """

        train_data, test_data, train_idx, test_idx = self.train_test_split(df, test_size=self.test_size)

        X_train, y_train = self.split_on_labels(train_data)
        X_test, y_test = self.split_on_labels(test_data)

        X_train = self.scaler.fit_transform(X_train).astype(np.float32)
        X_test = self.scaler.transform(X_test).astype(np.float32)
        y_train = y_train.to_numpy(dtype=np.float32)
        y_test = y_test.to_numpy(dtype=np.float32)

        X_train = self.to_windows(X_train)
        X_test = self.to_windows(X_test)
        y_train = self.to_windows(y_train)
        y_test = self.to_windows(y_test)

        return X_train, X_test, y_train, y_test, train_idx, test_idx

    def pretrain_final(self, df: pd.DataFrame) -> (np.array, np.array):
        """Prepare the data for training

        It splits the data into train and test sets, standardizes the data according to the train set,
        splits the data into features and labels, and converts the data to a numpy array.

        :param df: the dataframe to pretrain on
        :return: the train data, test data, train labels, test labels, train indices and test indices
        """

        X_train, y_train = self.split_on_labels(df)
        X_train = self.scaler.fit_transform(X_train).astype(np.float32)
        y_train = y_train.to_numpy(dtype=np.float32)

        X_train = self.to_windows(X_train)
        y_train = self.to_windows(y_train)

        return X_train, y_train

    def preprocess(self, x_data: pd.DataFrame) -> np.array:
        """Prepare the data for submission

        The data is supposed to be processed the same way as for the training and testing data.

        :param x_data: the dataframe to preprocess
        :return: the processed data
        """
        x_data = self.get_features(x_data)
        x_data = self.scaler.transform(x_data).astype(np.float32)
        return self.to_windows(x_data)

    @staticmethod
    def train_test_split(df: pd.DataFrame, test_size: float = 0.2) -> (pd.DataFrame, pd.DataFrame, np.array, np.array):
        """Split data into train and test on series id using GroupShuffleSplit

        :param df: the dataframe to split
        :param test_size: the size of the test set
        :return: the train data, test data, train indices and test indices
        """
        groups = df["series_id"]
        gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=42)
        train_idx, test_idx = next(gss.split(df, groups=groups))
        train_data = df.iloc[train_idx]
        test_data = df.iloc[test_idx]

        return train_data, test_data, train_idx, test_idx

    @staticmethod
    def get_features(df: pd.DataFrame) -> pd.DataFrame:
        """Split the labels from the features

        :param df: the dataframe to split
        :return: the data and features
        """
        feature_cols = [col for col in df.columns if col.startswith('f_')]

        return df[['enmo', 'anglez'] + feature_cols]

    @staticmethod
    def split_on_labels(df: pd.DataFrame) -> (pd.DataFrame, pd.DataFrame):
        """Split the data from the labels

        :param df: the dataframe to split
        :return: the data + features (1) and labels (2)
        """
        feature_cols = [col for col in df.columns if col.startswith('f_')]

        keep_columns: list[str] = ["awake", "onset", "wakeup", "onset-NaN", "wakeup-NaN",
                                   "hot-asleep", "hot-awake", "hot-NaN"]
        keep_y_train_columns: list = [column for column in keep_columns if column in df.columns]

        return df[['enmo', 'anglez'] + feature_cols], df[keep_y_train_columns]

    @staticmethod
    def to_windows(arr: np.ndarray) -> np.array:
        """Convert an array to a 3D tensor with shape (window, window_size, n_features)

        It's really just a simple reshape, but specifically for the windows.
        17280 is the number of steps in a window.

        :param arr: the array to convert, with shape (dataset length, number of columns)
        :return: the numpy array
        """
        return arr.reshape(-1, 17280, arr.shape[-1])
