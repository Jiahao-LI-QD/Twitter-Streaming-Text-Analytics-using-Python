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
import re
from nltk.sentiment.vader import SentimentIntensityAnalyzer as SIA

sia = SIA()




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

# clear the special characters
def clean_tweet(tweet):
        '''
        Utility function to clean tweet text by removing links, special characters
        using simple regex statements.
        '''
        return ' '.join(re.sub("(@[A-Za-z0-9]+)|([^0-9A-Za-z \t])|(\w+:\/\/\S+)", " ", tweet).split())

# return the sentiment value of the tweet
# -1 if negative, 0 if neutral, 1 if positive
def get_tweet_sentiment(tweet):
        '''
        Utility function to classify sentiment of passed tweet
        using textblob's sentiment method
        '''
        # create TextBlob object of passed tweet text
        pol_score = sia.polarity_scores(tweet)
        # set sentiment
        if pol_score['compound'] == 0:
            return 0
        elif pol_score['compound'] > 0:
            return 1
        else:
            return -1

#list of the topic and their corresponding hashtags
Amazon = ["#Amazon", "#amazonprime", "#amazondiscount", "#amazondeals", "#amazonfashion", "#amazonmusic", "#amazonfinds", "#amazonreviewer",  "#amazonfba", "#amazonseller"]
Ms = ["#microsoft", "#windows", "#windows10",  "#microsoftexcel", "#microsoftteams", "#microsoftpaint", "#microsoftoffice", "#microsoftstudios", "#microsoftstore", "#microsoftword"]
Fb = ["#facebooklive", "#facebookads", "#facebookpage", "#facebookmarketing", "#facebook", "#ins", "#instagram", "#facebookmemories", "#facebookmemes", "#facebookshop"]
apple = ["#apple", "#iphone", "#macbook", "#ipad", "#applewatch", "#ios", "#os", "#macbookpro", "#airpods", "#applestore"]
Google = ["#android","#google","#androidapp", "#googlemap", "#googleplay", "#googlepixel", "#googletrends", "#googleservice", "#gmail","#googledrive"]
keys = Amazon + Ms + Fb + apple + Google

# check if there exists hashtags (in the list L) in string s
def test_exist(s, L): 
    w = s.lower()
    for i in L:
        if i in w:
            return True
    return False

# check which topic this string belongs to (in the list L) in string s
def test_hashless(s, L):
    Hl = []
    for i in L:
        Hl.append(re.sub("#",'', i))
    return test_exist(s, Hl)

# return pair of (key, sentiment_value)
# key is the topic of this tweet
# value will be -1 if negative, 0 if neutral, 1 if positive
def sentiment(tweet):
    if test_hashless(tweet, Amazon):
        return ("Amazon: Avg. of ", get_tweet_sentiment(tweet))
    elif test_hashless(tweet, Ms):
        return ("Microsoft: Avg. of ", get_tweet_sentiment(tweet))
    elif test_hashless(tweet, Fb):
        return ("Facebook: Avg. of ", get_tweet_sentiment(tweet))
    elif test_hashless(tweet, apple):
        return ("Apple: Avg. of ", get_tweet_sentiment(tweet))
    elif test_hashless(tweet, Google):
        return ("Google: Avg. of ", get_tweet_sentiment(tweet))

#return which topic this tweet belongs to
def count_up(tweet):
    if test_hashless(tweet, Amazon):
        return ("Amazon: Avg. of ", 1)
    elif test_hashless(tweet, Ms):
        return ("Microsoft: Avg. of ", 1)
    elif test_hashless(tweet, Fb):
        return ("Facebook: Avg. of ", 1)
    elif test_hashless(tweet, apple):
        return ("Apple: Avg. of ", 1)
    elif test_hashless(tweet, Google):
        return ("Google: Avg. of ", 1)

# filter the stream with the list and clean the tweet        
lines = dataStream.filter(lambda x: test_exist(x,keys)).map(clean_tweet)

# map each hashtag to be a pair of (hashtag, 1)
hashtag_counts = lines.map(count_up)

# map each hashtag to be a pair of (hashtag, sentiment)
sentiment_counts = lines.map(sentiment)

# send the value pair to dashboard
def send_df_to_dashboard(df):
    # extract the hashtags from dataframe and convert them into array
    top_tags = [str(t.hashtag) for t in df.select("hashtag").collect()]
    # extract the counts from dataframe and convert them into array
    tags_count = [p.hashtag_count for p in df.select("hashtag_count").collect()]
    # initialize and send the data through REST API
    url = 'http://host.docker.internal:5002/updateData'
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
sentiment_totals = sentiment_counts.updateStateByKey(aggregate_tags_count)


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

# calculate the average for all the topics
def div(x):
    a = x[1][0]
    b = x[1][1]
    r = float(a) / b
    return (x[0] + str(b) + " occurrence", str(round(r,2)) )

# for each items in RDD join them to be (key, (sum_of_sentiment, count_of_occurrence))
result = sentiment_totals.join(hashtag_totals)

# result
final = result.map(div)
final.foreachRDD(process_interval)



# start the streaming computation
ssc.start()
# wait for the streaming to finish
ssc.awaitTermination()