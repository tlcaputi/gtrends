#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Pull and merge data from the Google Trends API

Copyright (c) 2020 Theodore L Caputi

"""

from googleapiclient.discovery import build
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
import tempfile
import shutil
import pandas as pd
import math
import functools
import numpy as np
import re
import sys
import statistics



def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3


def theo_timeline(terms, names, start, end, timeframe_list,
                  outpath, creds, timestep_years = 1, geo_country_list = [None],
                  geo_dma_list  = [None], geo_region_list  = [None],
                  worldwide = False, batch_size = 30, us_states = False,
                  rm_US_ = True):
    '''
    The Google Trends API is set up to provide data for a limited number of terms over a single geography and a single date period.
    This is a simple function that queries the Google Trends API for data for an unlimited number of search terms over multiple date
    periods and multiple geographies. Further, this function merges the data into term-level CSV files with geography as the columns
    and date as the index. When creating these term-level CSV files, it accounts for differences in overlapping data pulled from the API.
    '''

    # Set us_states = True to get all the states
    if us_states:
        geo_region_list = geo_region_list + [
                        'US-DC', 'US-AL', 'US-AK', 'US-AZ', 'US-AR', 'US-CA', 'US-CO', 'US-CT', 'US-DE', 'US-FL', 'US-GA', 'US-HI', 'US-ID', 'US-IL',
                        'US-IN', 'US-IA', 'US-KS', 'US-KY', 'US-LA', 'US-ME', 'US-MD', 'US-MA', 'US-MI', 'US-MN', 'US-MS', 'US-MO', 'US-MT', 'US-NE',
                        'US-NV', 'US-NH', 'US-NJ', 'US-NM', 'US-NY', 'US-NC', 'US-ND', 'US-OH', 'US-OK', 'US-OR', 'US-PA', 'US-RI', 'US-SC', 'US-SD',
                        'US-TN', 'US-TX', 'US-UT', 'US-VT', 'US-VA', 'US-WA', 'US-WV', 'US-WI', 'US-WY'
                        ]
        geo_region_list = sorted(list(set([x for x in geo_region_list if x])))


    # Set parameters
    global API_KEY
    global SERVER
    global API_VERSION
    global DISCOVERY_URL_SUFFIX
    global DISCOVERY_URL

    f = open(creds, 'r')
    for line in f:
        exec(line, globals())


    # Change timestep into relativedelta format
    timestep = relativedelta(years=timestep_years)


    # Make the start and end date into datetime format
    start_date = datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.strptime(end, '%Y-%m-%d')


    # Run some assert statements to make sure things will work out
    assert "linux" in sys.platform or "win" in sys.platform, "Wrong Operating System"
    assert sys.version[0] == '3', "Wrong Python Version"
    assert batch_size < 30, "Batch Size must be lower than 30"
    assert len(terms) == len(names), "Number of terms not the same as the number of names"
    assert start_date < end_date, "Start date is after the end date (or not valid)"
    for tf in timeframe_list:
        assert tf in ['year', 'month', 'week', 'day'], "Incorrect timeframe"


    service = build('trends', 'v1beta',
                  developerKey=API_KEY,
                  discoveryServiceUrl=DISCOVERY_URL)




    # We want all of the different geographies in the same term-level CSV file. Therefore, we need to combine all the geographies
    # into the same list but keep track of what kind of geography they are
    all_locations = [geo_country_list, geo_dma_list, geo_region_list]
    locations = []
    locations_type = []
    which_list = 0

    # This for loop rules out all of the 'None' observations in the list
    for lis in all_locations:
        for item in lis:
            if item:
                locations = locations + [item]
                if which_list == 0:
                    locations_type = locations_type + ['geo_country']
                elif which_list == 1:
                    locations_type = locations_type + ['geo_dma']
                elif which_list == 2:
                    locations_type = locations_type + ['geo_region']
        which_list = which_list + 1


    # If you want worldwide data, you need to set all geographies to None
    if worldwide:
        locations = locations + [None]
        locations_type = locations_type + ["geo_region"]




    # We do different timeframes separately
    for timeframe in timeframe_list:

        # We first look at a group of terms. For that group of terms...
        batch_start = 0
        while len(terms) - (batch_start + 1) >= 0:

            batch_end = min(batch_start + batch_size, len(terms))
            term_batch = terms[batch_start:batch_end]
            name_batch = names[batch_start:batch_end]
            batch_start = batch_start + batch_size

            print("[{}] BATCH: {}".format(datetime.now().strftime("%H:%M:%S"), term_batch))


            name_list = []
            period_list = []
            location_list = []
            df_list = []


            # We pull a certain date range
            period = 0
            date1 = start_date
            date2 = min(date1 + timestep, end_date)

            while date1 < end_date and (date1 + timestep < end_date or period == 0):

                if period != 0:
                    date1 = date1 + timestep
                    date2 = min(date2 + timestep, end_date)
                period = period + 1

                print('[{}] TIMEPERIOD: FROM {} TO {}'.format(datetime.now().strftime("%H:%M:%S"), date1.strftime('%Y-%m-%d'), date2.strftime('%Y-%m-%d')))


                # For this term X date range combination, we pull all possible geographies
                for loc_ind in range(0, len(locations)):
                    location = locations[loc_ind]
                    location_type = locations_type[loc_ind]

                    print("[{}] LOCATION: {}".format(datetime.now().strftime("%H:%M:%S"), location))


                    # We use the locations_type list from before to determine what kind of geography each geography is
                    if location_type == 'geo_country':
                        geo_country = location
                        geo_dma = None
                        geo_region = None
                    elif location_type == 'geo_dma':
                        geo_country = None
                        geo_dma = location
                        geo_region = None
                    elif location_type == 'geo_region':
                        geo_country = None
                        geo_dma = None
                        geo_region = location


                    # This actually queries the API
                    response = service.getTimelinesForHealth(
                        terms=term_batch,
                        time_startDate=date1.strftime('%Y-%m-%d'),
                        time_endDate=date2.strftime('%Y-%m-%d'),
                        timelineResolution=timeframe,
                        geoRestriction_country=geo_country,
                        geoRestriction_dma=geo_dma,
                        geoRestriction_region=geo_region).execute()




                    # We reformat the data from the API into pandas
                    data = response['lines']
                    for ind in range(0, len(data)):

                        name = name_batch[ind]

                        df = pd.DataFrame(data[ind]['points'])
                        df = df.rename(columns={'date': 'timestamp', 'value': location})

                        if timeframe == 'year':
                            df['timestamp'] = pd.to_datetime(pd.Series(df['timestamp']), format = '%Y')
                        elif timeframe == 'month':
                            df['timestamp'] = pd.to_datetime(pd.Series(df['timestamp']), format = '%b %Y')
                        else:
                            df['timestamp'] = pd.to_datetime(pd.Series(df['timestamp']), format = '%b %d %Y')



                        # For each term X date range X geography combination, we append the data to a list
                        # and keep track of its term, date range, and geography in separate lists
                        name_list = name_list + [name]
                        period_list = period_list + [period]
                        location_list = location_list + [location]
                        df_list = df_list + [df]




            # The first step is to bind the rows of datasets that have the same term X geography but
            # different date ranges
            terms_in_batch = sorted(list(set(name_list)))
            locations_in_batch = list(set(location_list))
            periods_in_batch = sorted(list(set(period_list)))
            binded_df_list = []
            binded_term_list = []

            for location_in_batch in locations_in_batch:
                for term_in_batch in terms_in_batch:

                    cond1 = [True if x == term_in_batch else False for x in name_list]
                    cond2 = [True if x == location_in_batch else False for x in location_list]
                    indexes_cond1 = [i for i, v in enumerate(cond1) if v]
                    indexes_cond2 = [i for i, v in enumerate(cond2) if v]
                    indexes_for_location_term = intersection(indexes_cond1, indexes_cond2)
                    data_to_bind = [df_list[i] for i in indexes_for_location_term]

                    # This appends the binded data
                    binded_data = data_to_bind[0]
                    for data_ind in range(1, len(data_to_bind)):
                        binded_data = binded_data.append(data_to_bind[data_ind])

                    # and we save it to a list of binded dataframes
                    binded_df_list = binded_df_list + [binded_data]
                    binded_term_list = binded_term_list + [term_in_batch]


            # Finally, we need to merge the columns of binded datasets with data for the same term but different locations
            terms_in_batch = sorted(list(set(binded_term_list)))
            for term_in_batch in terms_in_batch:

                matches = [True if x == term_in_batch else False for x in binded_term_list]
                indexes_for_term = [i for i, v in enumerate(matches) if v]
                data_to_merge = [binded_df_list[i] for i in indexes_for_term]


                def if0NA(data):
                    return([None if x == 0 else x for x in data])

                def mean0(data):
                    if all([True if not x else False for x in data]):
                        return -9999
                    else:
                        out = statistics.mean([x for x in data if x])
                        return out

                def rev9999(data):
                    return [x if x != -9999 else None for x in data]


                merged_data = data_to_merge[0]
                merged_data.iloc[:,1] = [x if x != 0 else None for x in merged_data.iloc[:,1]]
                merged_data = merged_data.groupby('timestamp').agg(mean0)
                for data_ind in range(1, len(data_to_merge)):
                    data_about_to_be_merged = data_to_merge[data_ind]
                    # Fix duplicate rows
                    data_about_to_be_merged.iloc[:,1] = [x if x != 0 else None for x in data_about_to_be_merged.iloc[:,1]]
                    data_about_to_be_merged = data_about_to_be_merged.groupby('timestamp').agg(mean0)
                    # Merge the data
                    merged_data = merged_data.merge(data_about_to_be_merged, on='timestamp')


                # Unfortunately, the API provides a lot of overlap. For all dates with multiple observations,
                # we take the mean (removing NA values and 0 values)
                merged_data = merged_data.apply(rev9999)
                merged_data.sort_values(by='timestamp')
                merged_data.columns = ["Worldwide" if not x else x for x in merged_data.columns]
                merged_data.columns = [re.sub("[-]", "_", x) for x in merged_data.columns.tolist()]

                # Option to remove US_ from state label names
                if rm_US_ is True:
                    colnames = [re.sub("US_", "", x) for x in merged_data.columns.tolist()]
                    # It will only change the column names if they are still unique after removing the US_
                    if len(set(colnames)) == len(colnames):
                        merged_data.columns = colnames

                # Finally we save the merged, binded data to a CSV for further analysis
                merged_data.to_csv("{}/{}_{}.csv".format(outpath, term_in_batch, timeframe))
                print("[{}] {}_{}.csv created!".format(datetime.now().strftime("%H:%M:%S"), term_in_batch, timeframe))


    def main():

        theo_timeline(
            terms = ['cats', 'cats + food'],
            names = ['cats', 'food'],
            start = '2019-01-01',
            end = '2020-01-01',
            timeframe_list = ['year'],
            geo_country_list = ['US'],
            worldwide = False,
            timestep_years = 1,
            batch_size = 2,
            us_states = True,
            outpath = "C:/Users/tcapu/Google Drive/PublicHealthStudies/cats",
            creds = "C:/Users/tcapu/Google Drive/modules/gtrendspy/info_theo.py"
        )

if __name__ == "main":
    main()
