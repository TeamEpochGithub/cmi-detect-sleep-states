import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from tqdm import tqdm

from ..logger.logger import logger
from ..preprocessing.pp import PP, PPException


@dataclass
class AddStateLabels(PP):
    """Adds state labels to each row of the data

    The state labels are added to the "awake" column based on the events csv file.
    The values are 0 for asleep, 1 for awake, and 2 for unlabeled.

    :param events_path: the path to the events csv file
    :param use_similarity_nan: If True, use the similarity_nan column to fill in the awake column
    :param fill_limit: The maximum number of steps to fill in the awake column
    :param nan_tolerance_window: The number of steps to tolerate NaNs before filling in the awake column
    """
    events_path: str
    use_similarity_nan: bool
    fill_limit: int | None = None
    nan_tolerance_window: int = 1

    def __post_init__(self) -> None:
        """Check if the fill_limit is set when using similarity NaN

        :raises PPException: If the fill_limit is not set when using similarity NaN
        """
        if self.use_similarity_nan and self.fill_limit is None:
            logger.critical("fill_limit is required when using similarity NaN")
            raise PPException("fill_limit is required when using similarity NaN")

    def run(self, data: dict) -> dict:
        """Run the preprocessing step.

        :param data: the data to preprocess
        :return: the preprocessed data
        :raises FileNotFoundError: If the events csv or id_encoding json file is not found
        """
        self.events = pd.read_csv(self.events_path)
        res = self.preprocess(data)
        del self.events
        return res

    def preprocess(self, data: dict) -> dict:
        """Preprocess the data by adding state labels to each row of the data.

        :param data: the data without state labels
        :return: the data with state labels added to the "awake" column
        """

        # Initialize the awake column as 42, to catch errors later (-1 not possible in uint8)

        for sid in data.keys():
            data[sid]['awake'] = 42
            data[sid]['awake'] = data[sid]['awake'].astype('uint8')

        # get columns from some arbitrary frame
        columns = next(iter(data.values())).columns

        # Hand-picked weird cases, with unlabeled, non-nan tails
        # the ids are hard-coded as full id strings, require encoding fist
        weird_series = ["0cfc06c129cc", "31011ade7c0a", "55a47ff9dc8a", "a596ad0b82aa", "a9a2f7fac455"]

        # iterate over the series and set the awake column
        if self.use_similarity_nan:
            similarity_cols = [col for col in columns if col.endswith('similarity_nan')]
            if len(similarity_cols) == 0:
                raise Exception("No (f_)similarity_nan column found, but use_similarity_nan is set to True")
            tqdm.pandas()
            for sid in data.keys():
                data[sid] = self.set_awake_with_similarity(data[sid], similarity_cols[0], sid).reset_index(drop=True)
        else:
            tqdm.pandas()
            for sid in data.keys():
                data[sid] = self.set_awake(data[sid], weird_series, sid).reset_index(drop=True)

        return data

    def set_awake(self, series, weird_series_encoded, sid):
        awake_col = series.columns.get_loc('awake')
        series_id = sid
        current_events = self.events[self.events["series_id"] == series_id]
        if len(current_events) == 0:
            series['awake'] = 2
            return series

        # iterate over event labels and fill in the awake column segment by segment
        prev_step = 0
        prev_was_nan = False
        for _, row in current_events.iterrows():
            step = row['step']
            if np.isnan(step):
                prev_was_nan = True
                continue

            step = int(step)
            if prev_was_nan:
                series.iloc[prev_step:step, awake_col] = 2
            elif row['event'] == 'onset':
                series.iloc[prev_step:step, awake_col] = 1
            elif row['event'] == 'wakeup':
                series.iloc[prev_step:step, awake_col] = 0
            else:
                raise Exception(f"Unknown event type: {row['event']}")

            prev_step = step
            prev_was_nan = False

        # set the tail based on the last event, unless it's a weird series, which has a NaN tail
        last_event = current_events['event'].tail(1).values[0]
        if prev_was_nan:
            series.iloc[prev_step:, awake_col] = 2
        elif series_id in weird_series_encoded:
            series.iloc[prev_step:, awake_col] = 2
        elif last_event == 'wakeup':
            series.iloc[prev_step:, awake_col] = 1
        elif last_event == 'onset':
            series.iloc[prev_step:, awake_col] = 0
        return series

    def set_awake_with_similarity(self, series, similarity_col_name, sid):
        """Set awake using nan_similarity, adds labels of 2 (nan) or 3 (unlabeled)"""
        awake_col = series.columns.get_loc('awake')
        series_id = sid
        current_events = self.events[self.events["series_id"] == series_id]
        if len(current_events) == 0:
            series['awake'] = 2
            return series

        # initialize as unlabeled, and set nan based on similarity_nan
        series['awake'] = 3
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            series['awake'][series[similarity_col_name] == 0] = 2

        # iterate over event labels and fill in the awake column segment by segment
        prev_step = 0
        prev_event = None

        fill_value_before = {
            "onset": 1,
            "wakeup": 0,
        }
        fill_value_after = {
            "onset": 0,
            "wakeup": 1,
        }

        for _, row in current_events.iterrows():
            step = row['step']

            if np.isnan(step):
                if prev_event != 'nan' and prev_event is not None:
                    # transition from non-nan to nan
                    self.fill_forward(awake_col, fill_value_after[prev_event], prev_step, series)
                prev_event = 'nan'
            else:
                step = int(step)
                event = row['event']
                if prev_event == 'nan':
                    # transition from nan to non-nan
                    self.fill_backward(awake_col, fill_value_before[event], prev_step, series, step)
                else:
                    # non-nan to non-nan segment
                    series.iloc[prev_step:step, awake_col] = fill_value_before[event]

                prev_step = step
                prev_event = event

        # fill in the tail of the series after the last event
        if prev_event is not None and prev_event != 'nan':
            self.fill_forward(awake_col, fill_value_after[prev_event], prev_step, series)
        return series

    def fill_backward(self, awake_col, fill_value, prev_step, series, step):
        """Fill in the awake column backwards from step to the last non-nan similar value, up to a limit"""
        search_slice = series.iloc[prev_step:step, awake_col]
        slice_similar_mask = (search_slice == 2).rolling(self.nan_tolerance_window).median()

        # weird trick, argmax returns the index of the first occurrence of the max value,
        # so we reverse it twice to get the last index where the mask is 1 (the max value)
        last_similar = slice_similar_mask[::-1].argmax()
        start_of_fill = step - last_similar

        start_of_fill = max(start_of_fill, step - self.fill_limit)
        series.iloc[start_of_fill:step, awake_col] = fill_value

    def fill_forward(self, awake_col, fill_value, prev_step, series):
        """Fill in the awake column forward from prev_step to the first non-nan similar value, up to a limit"""
        search_slice = series.iloc[prev_step:prev_step + self.fill_limit, awake_col]
        slice_similar_mask = (search_slice == 2).rolling(self.nan_tolerance_window).median()
        first_similar = slice_similar_mask.argmax()
        if slice_similar_mask.any():
            end_of_fill = prev_step + first_similar
            end_of_fill = min(end_of_fill, prev_step + self.fill_limit)
        else:
            end_of_fill = prev_step + self.fill_limit
        series.iloc[prev_step:end_of_fill, awake_col] = fill_value
