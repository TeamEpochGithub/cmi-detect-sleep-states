# This class is to reduce memory usage of dataframe
from ..preprocessing.pp import PP
from ..logger.logger import logger
import json
import pandas as pd
import polars as pl


class MemReduce(PP):

    def preprocess(self, data):
        df = self.reduce_mem_usage(data)
        return df

    def reduce_mem_usage(self, data: pd.DataFrame) -> pd.DataFrame:
        # we should make the series id in to an int16
        # and save an encoding (a dict) as a json file somewhere
        # so we can decode it later
        encoding = dict(zip(data['series_id'].unique(), range(len(data['series_id'].unique()))))
        filename = 'series_id_encoding.json'
        with open(filename, 'w') as f:
            json.dump(encoding, f)
        logger.debug(f"------ Done saving series encoding to {filename}")
        data['series_id'] = data['series_id'].map(encoding)
        data['series_id'] = data['series_id'].astype('int16')

        # putting this after the int16 conversion makes it reduce memory
        # a lot more than if we put it before
        if not self.use_pandas:
            if isinstance(data, pd.DataFrame):
                data = pl.from_pandas(data)
        data = pl.from_pandas(data)
        data = data.with_columns(pl.col("timestamp").str.slice(0, 18).alias("datetime"))
        data = data.with_columns(pl.col("datetime").str.to_datetime(format="%Y-%m-%dT%H:%M:%S").cast(pl.Datetime))
        logger.debug("------ Done converting timestamp to datetime")
        # remove the timestamp column
        data = data.drop("timestamp")
        data = data.to_pandas()
        return data
