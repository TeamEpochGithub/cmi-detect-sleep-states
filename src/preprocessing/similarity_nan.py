from src.preprocessing.pp import PP
import numpy as np
from tqdm import tqdm
import pandas as pd


class SimilarityNan(PP):
    def preprocess(self, data: pd.DataFrame) -> pd.DataFrame:
        tqdm.pandas()
        data = (data.groupby('series_id')
                .progress_apply(similarity_nan)
                .reset_index(0, drop=True))
        return data


def similarity_nan(series):
    """Computes the similarity of each point to that at the same time in the last 24h hours"""
    STEPS_PER_DAY = (24 * 60 * 60) // 5

    if len(series) < STEPS_PER_DAY:
        return np.zeros(len(series))

    # pad the series to a multiple of steps per day
    feature_np = series['anglez'].to_numpy()
    padded = np.pad(feature_np, (0, STEPS_PER_DAY - (len(series) % STEPS_PER_DAY)), 'constant', constant_values=0)

    # compute the absolute difference between each day
    days = len(padded) // STEPS_PER_DAY
    comparison = np.empty((days, len(padded)))
    for day in range(days):
        day_data = padded[day * STEPS_PER_DAY: (day + 1) * STEPS_PER_DAY]
        tiled = np.tile(day_data, days)
        comparison[day] = np.abs(tiled - padded)

    # set the self comparisons to inf
    for day in range(days):
        comparison[day, day * STEPS_PER_DAY: (day + 1) * STEPS_PER_DAY] = np.inf

    # get the minimum
    diff = np.min(comparison, axis=0)

    # add the diff to the series as a column of float32
    series['f_similarity_nan'] = diff[:len(feature_np)].astype(np.float32)
    return series
