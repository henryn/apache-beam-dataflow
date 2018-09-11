import os
import logging
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.options.pipeline_options import SetupOptions
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.options.pipeline_options import StandardOptions
from apache_beam.io import ReadFromText, WriteToText


input_filename = 'gs://hn-dataflow-intro/input-1gb.txt'
output_filename = 'gs://hn-dataflow-intro/output.txt'

dataflow_options = ['--project=hnacino-sandbox', '--job_name=test-job', '--temp_location=gs://hn-dataflow-intro/temp']
dataflow_options.append('--staging_location=gs://hn-dataflow-intro/stage')
options = PipelineOptions(dataflow_options)
gcloud_options = options.view_as(GoogleCloudOptions)

# Dataflow runner
options.view_as(StandardOptions).runner = 'dataflow'

class Split(beam.DoFn):
    def process(self, element):
        """
        Splits each row on commas and returns a dictionary representing the
        row
        """
        country, duration, user = element.split(",")
        return [{
            'country': country,
            'duration': float(duration),
            'user': user
        }]


class CollectTimings(beam.DoFn):
    def process(self, element):
        """
        Returns a list of tuples containing country and duration
        """
        result = [
            (element['country'], element['duration'])
        ]
        return result


class CollectUsers(beam.DoFn):
    def process(self, element):
        """
        Returns a list of tuples containing country and user name
        """
        result = [
            (element['country'], element['user'])
        ]
        return result


class WriteToCSV(beam.DoFn):
    def process(self, element):
        """
        Prepares each row to be written in the csv
        """
        result = [
            "{},{},{}".format(
                element[0],
                element[1]['users'][0],
                element[1]['timings'][0]
            )
        ]
        return result

with beam.Pipeline(options=options) as p:
    rows = (
        p |
        beam.io.ReadFromText(input_filename) |
        beam.ParDo(Split())
    )

    timings = (
        rows |
        beam.ParDo(CollectTimings()) |
        "Grouping timings" >> beam.GroupByKey() |
        "Calculating average" >> beam.CombineValues(beam.combiners.MeanCombineFn()
        )
    )

    users = (
        rows |
        beam.ParDo(CollectUsers()) |
        "Grouping users" >> beam.GroupByKey() |
        "Counting users" >> beam.CombineValues(beam.combiners.CountCombineFn()
        )
    )

    to_be_joined = (
        {
            'timings': timings,
            'users': users
        } |
            beam.CoGroupByKey() |
            beam.ParDo(WriteToCSV()) |
            beam.io.WriteToText(output_filename)
    )