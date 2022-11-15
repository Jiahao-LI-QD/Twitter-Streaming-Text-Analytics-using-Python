"""
    This Spark app connects to a script running on another (Docker) machine
    on port 9009 that provides a stream of raw tweets text. That stream is
    meant to be read and processed here, where top trending hashtags are
    identified. Both apps are designed to be run in Docker containers.

    To execute this in a Docker container, do:
    
        docker run -it -v $PWD:/app --link twitter:twitter eecsyorku/eecs4415

    and inside the docker:

        spark-submit spark_app.py

    For more instructions on how to run, refer to final tutorial 8 slides.

    Made for: EECS 4415 - Big Data Systems (York University EECS dept.)
    Modified by: Tilemachos Pechlivanoglou
    Based on: https://www.toptal.com/apache/apache-spark-streaming-twitter
    Original author: Hanee' Medhat

"""

from pyspark import SparkConf,SparkContext
from pyspark.streaming import StreamingContext
from pyspark.sql import Row,SQLContext
import sys
import requests





# create spark configuration
conf = SparkConf()
conf.setAppName("TwitterStreamApp")
# create spark context with the above configuration
sc = SparkContext(conf=conf)
sc.setLogLevel("ERROR")
# create the Streaming Context from spark context, interval size 2 seconds
ssc = StreamingContext(sc, 2)
# setting a checkpoint for RDD recovery (necessary for updateStateByKey)
ssc.checkpoint("checkpoint_TwitterApp")
# read data from port 9009
dataStream = ssc.socketTextStream("twitter",9009)

# reminder - lambda functions are just anonymous functions in one line:
#
#   words.flatMap(lambda line: line.split(" "))
#
# is exactly equivalent to
#
#    def space_split(line):
#        return line.split(" ")
#
#    words.filter(space_split)

# split each tweet into words
words = dataStream.flatMap(lambda line: line.split(" "))

# filter the words to get only hashtags
# convert from words to lower case, calling itself
lowerwords = words.map(lambda x: x.lower())

#equal to lamda word:
hashtags = lowerwords.filter(lambda w: ('#laker' in w) or ('#76er' in w) or ('#suns' in w) or ('#hawk' in w) or ('#clipper' in w))
# '#lakers', '#76ers', '#hawks', '#utahjazz', '#clippers'
# dictionary to be ploted
def rec(w):
    if '#laker' in w:
        return ("#Lakers", 1)
    elif '#76er' in w:
        return ("#76ers", 1)
    elif '#suns' in w:
        return ("#Suns", 1)
    elif '#hawk' in w:
        return ("#Hawks", 1)
    elif '#clipper' in w:
        return ('#Clippers', 1)

# map each hashtag to be a pair of (hashtag,1)
hashtag_counts = hashtags.map(rec)


# def send_df_to_dashboard(dict):
#     # extract the hashtags from dataframe and convert them into array
#     top_tags = dict.keys()
#     # extract the counts from dataframe and convert them into array
#     tags_count = dict.values()
#     # initialize and send the data through REST API
#
#     url = 'http://localhost/refreshData'
#     request_data = {'label': str(top_tags), 'data': str(tags_count)}
#     # response = requests.post(url, data=request_data)


def send_df_to_dashboard(df):
    # extract the hashtags from dataframe and convert them into array
    top_tags = [str(t.hashtag) for t in df.select("hashtag").collect()]
    # extract the counts from dataframe and convert them into array
    tags_count = [p.hashtag_count for p in df.select("hashtag_count").collect()]
    # initialize and send the data through REST API
    url = 'http://host.docker.internal:5001/updateData'
    request_data = {'label': str(top_tags), 'data': str(tags_count)}
    response = requests.post(url, data=request_data)


# adding the count of each hashtag to its last count
def aggregate_tags_count(new_values, total_sum):
    return sum(new_values) + (total_sum or 0)

def get_sql_context_instance(spark_context):
    if ('sqlContextSingletonInstance' not in globals()):
        globals()['sqlContextSingletonInstance'] = SQLContext(spark_context)
    return globals()['sqlContextSingletonInstance']


# do the aggregation, note that now this is a sequence of RDDs
hashtag_totals = hashtag_counts.updateStateByKey(aggregate_tags_count)


# process a single time interval
def process_interval(time, rdd):
    # print a separator
    print("----------- %s -----------" % str(time))

    try:
        # sort counts (desc) in this time instance and take top 10
        sorted_rdd = rdd.sortBy(lambda x:x[1], False)
        top10 = sorted_rdd.take(10)
        sql_context = get_sql_context_instance(rdd.context)
        # # convert the RDD to Row RDD
        row_rdd = rdd.map(lambda w: Row(hashtag=w[0], hashtag_count=w[1]))
        # create a DF from the Row RDD
        hashtags_df = sql_context.createDataFrame(row_rdd)
        # Register the dataframe as table
        hashtags_df.registerTempTable("hashtags")
        # get the top 10 hashtags from the table using SQL and print them
        hashtag_counts_df = sql_context.sql(
             "select hashtag, hashtag_count from hashtags order by hashtag_count desc limit 10")

        # call this method to prepare top 10 hashtags DF and send them
        send_df_to_dashboard(hashtag_counts_df)
        # print it nicely
        for tag in top10:
            print('{:<40} {}'.format(tag[0], tag[1]))

    except:
        e = sys.exc_info()[0]
        print("Error: %s" % e)

# do this for every single interval
hashtag_totals.foreachRDD(process_interval)



# start the streaming computation
ssc.start()
# wait for the streaming to finish
ssc.awaitTermination()