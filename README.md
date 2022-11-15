The application is about performing the data analysis on tweets from Twitter in real time, and the result will be displayed on the local network via browser.
The whole application is running on top of 3 python scripts together, some of them require a docker environment.

First in order to track occurrence of each hashtag and display in real time, for example the following(you can customize those hashtags accordingly) :
track = ['#laker', '#76er', '#hawk', '#jazz,nba', '#clipper'] in trend_twitter_app.py
hashtags = lowerwords.filter(lambda w: ('#laker' in w) or ('#76er' in w) or ('#jazz' in w) or ('#hawk' in w) or ('#clipper' in w))  in trend_spark_app.py
The dashboard needs to be activated first, and you can run it into local PC terminal:
python trend_chart_app.py

And you can see chart layer displayed in your browser at 127.0.0.1:5001
We need to run trend_twitter_app.py to connect and fetch the tweets from Twitter,. The consumer_key,consumer_secret, access_token and access_token_secret can be applied by Twitter developer account which are essential to connect with Twitter servers. trend_twitter_app.py is running in the following docker container:
docker run -it -v $PWD:/app --name twitter -w /app python bash

You might require:
pip install tweety
To install tweety library

Once trend_twitter_app.py is running by: python trend_twitter_app.py; you will receive message saying is waiting for TCP connection(waiting for connecting to spark), you are ready for the next step
trend_spark_app.py is used to receive data from trend_twitter_app.py and analyze in Spark. 
Trend_spark_app.py is running in the following docker environment:
docker run -p 5001:5001 -it -v $PWD:/app --link twitter:twitter eecsyorku/eecs4415
And run it by: 
spark-submit trend_spark_app.py

Second part of our application is to analysis the sentiment value of each tweets in different topic by using Natural Language Toolkit (NLTK )module in python (positive tweet:1, negative tweet:-1, neutral tweet:0) The topics are relative in the tech companies following by: Facebook, Amazon, Microsoft, Google and Apple, the average of sentimental value from tweets in each topic will be displayed
Similar to the processor of first part of our application, first the dashboard needs to be activated in your local PC terminal:
python sentiment_chart_app.py

And you can see chart layer displayed in your browser at 127.0.0.1:5002
Then we need to run sentiment_twitter_app.py in the same docker container as running trend_twitter_app.py 
The way to run sentiment_spark_app.py is slightly different because it is running in port 5002, so the docker container will be:
docker run -p 5002:5002 -it -v $PWD:/app --link twitter:twitter eecsyorku/eecs4415 
Then you can run: python sentiment_spark_app.py

Before get in to the instructions:
1. python container and eecs4415 container has the same path in your localhost
2. Make sure your web page file structure is the same as:
    ->static
        ->Chart.js
    ->templates
        ->sentiment_Chart.html
        ->trend_Chart.html
3. tweet is installed in python container
3. nltk is installed in eecs4415 container

---Steps to run Part.A Trend of 5 hashtags--------------------------------------------------------------------------------
1. Open terminal of python container
2. Open terminal of eecs4415 container, make sure it has linked to the python container and it has the access to prot 5001
3. Open terminal of your local host
4. In python container: 
    $ python trend_twitter_app.py
5. In eecs4415 container: 
    $ export PYSPARK_PYTHON=python3.5
    $ spark-submit trend_spark_app.py
6. In your localhost terminal:
    $ python trend_chart_app.py
7. Open 127.0.0.1:5001 in your browser, the chart will be displayed in the web page

---Steps to run Part.B Sentiment of 5 topics--------------------------------------------------------------------------------
1. Open terminal of python container
2. Open terminal of eecs4415 container, make sure it has linked to the python container and it has the access to prot 5002
3. Open terminal of your local host
4. In python container: 
    $ python sentiment_twitter_app.py
5. In eecs4415 container: 
    $ export PYSPARK_PYTHON=python3.5
    $ spark-submit sentiment_spark_app.py
6. In your localhost terminal:
    $ python sentiment_chart_app.py
7. Open 127.0.0.1:5002 in your browser, the chart will be displayed in the web page
