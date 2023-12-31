from spiders.spiders.wikicityspider import WikiCitySpider
from spiders.spiders.ongovschoolspider import OnGovSecSchoolIdSpider, OnGovElSchoolIdSpider, OnGovSchoolSpider
from spiders.spiders.zillowspider import ZillowcaSpider
from spiders.spiders.mortgagespider import MortgageRatesSpider
from spiders.spiders.airbnbspider import AirbnbSpider
from spiders.spiders.yelpapispider import YelpApiSpider
from spiders.spiders.walkscorespider import WalkScoreZillowSpider, WalkScoreRemaxSpider
from spiders.spiders.oncolunispider import OnGovUniListSpider, OnGovUniSpider,  OnGovColListSpider, OnGovColSpider
from scrapy.crawler import CrawlerRunner
from scrapy.signalmanager import dispatcher
from scrapy import signals
from twisted.internet import reactor, defer
from scrapy.utils.project import get_project_settings
from scrapy.utils.log import configure_logging
import warnings
import os
import mysql.connector
from dotenv import find_dotenv, load_dotenv
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)
from spiders.spiders.remaxspider import RemaxSpider

def main():
  warnings.filterwarnings("ignore")
  wikicity_output = []
  sec_schoolIds_output = []
  el_schoolIds_output = []
  universities = []
  colleges = []
  def crawler_results(item, spider):
    if spider.name == 'wikicity':
      wikicity_output.append(item)
    elif spider.name == 'ongovsecschoolid':
      sec_schoolIds_output.append(item)
    elif spider.name == 'ongovelschoolid':
      el_schoolIds_output.append(item)
    elif spider.name == 'ongovunilist':
      universities.append(item['university'])
    elif spider.name == 'ongovcollist':
      colleges.append(item['college'])
  dispatcher.connect(crawler_results, signal=signals.item_scraped)
  #The settings are required to override the default settings used
  #by the spiders.
  settings = {
    'SCRAPEOPS_API_KEY': os.getenv("SCRAPEOPS_API_KEY"),
    'SCRAPEOPS_FAKE_USER_AGENT_ENABLED': True,
    'DOWNLOADER_MIDDLEWARES': {
      'spiders.middlewares.ScrapeOpsFakeUserAgentMiddleware': 400,
      'scrapy_fake_useragent.middleware.RandomUserAgentMiddleware': 401,
      'scrapy_fake_useragent.middleware.RetryUserAgentMiddleware': 402,
      'rotating_proxies.middlewares.RotatingProxyMiddleware': 610,
      'rotating_proxies.middlewares.BanDetectionMiddleware': 620,
    },
    'HEADERS': {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.5",
      "Accept-Encoding": "gzip, deflate",
      "Connection": "keep-alive",
      "Upgrade-Insecure-Requests": "1",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
      "Sec-Fetch-User": "?1",
      "Cache-Control": "max-age=0",
    },
    'RETRY_ENABLED': True,
    'RETRY_TIMES': 5,
    'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429, 403],
    'RETRY_PRIORITY_ADJUST': -1,
    'RETRY_EXCEPTIONS': [
      "twisted.internet.defer.TimeoutError",
      "twisted.internet.error.TimeoutError",
      "twisted.internet.error.DNSLookupError",
      "twisted.internet.error.ConnectionRefusedError",
      "twisted.internet.error.ConnectionDone",
      "twisted.internet.error.ConnectError",
      "twisted.internet.error.ConnectionLost",
      "twisted.internet.error.TCPTimedOutError",
      "twisted.web.client.ResponseFailed",
    # OSError is raised by the HttpCompression middleware when trying to
    # decompress an empty response
      OSError,
      "scrapy.core.downloader.handlers.http11.TunnelError",
    ],
    #Logging Settings
    'LOG_FILE': f'/var/log/scrapy.log',
    'LOGGING_ENABLED': True,
    'LOGGING_LEVEL': 'Debug',
    'LOG_STDOUT': True,
    'LOG_FORMAT': "%(levelname)s: %(message)s",
    # Obey robots.txt rules
    'ROBOTSTXT_OBEY': False,
    # Set settings whose default value is deprecated to a future-proof value
    'REQUEST_FINGERPRINTER_IMPLEMENTATION': "2.7",
    # TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
    'FEED_EXPORT_ENCODING': "utf-8",
    'ITEM_PIPELINES': {
      "spiders.pipelines.MysqlPipeline": 100
    },
    'COOKIES_ENABLED': False,
    'DOWNLOAD_DELAY': 5
  }

  #MySQL Connection To Query Data for location coordinates
  conn = mysql.connector.connect(
    host = os.getenv("MYSQL_HOST"),
    user = os.getenv("MYSQL_USER"),
    password = os.getenv("MYSQL_PASSWORD"),
    database = 'DataAnalysis',
    port = '3306')
  cursor = conn.cursor(buffered=True , dictionary=True)
  configure_logging(settings)
  zillow_coordinates_query = ''' SELECT ZillowListings.Id, ST_X(ZillowListings.ListingCoordinates) AS lon, 
                                ST_Y(ZillowListings.ListingCoordinates) AS lat FROM ZillowListings WHERE NOT EXISTS 
                                (SELECT * FROM ZillowListingsWalkscore WHERE 
                                ZillowListingsWalkscore.Id = ZillowListings.Id) '''
  remax_coordinates_query = ''' SELECT RemaxListings.Id, ST_X(RemaxListings.ListingCoordinates) AS lon, 
                                ST_Y(RemaxListings.ListingCoordinates) AS lat FROM RemaxListings WHERE NOT EXISTS 
                                (SELECT * FROM RemaxListingsWalkscore WHERE 
                                RemaxListingsWalkscore.Id = RemaxListings.Id) '''
  #To add the city names from the city data collected from Wikipedia
  list_cities = []
  runner = CrawlerRunner(settings)
  @defer.inlineCallbacks
  def crawl():    
    yield runner.crawl(WikiCitySpider)
    for item in wikicity_output:
      # This filters the city names and append them to the list_cities array. 
      # By default the list contains two entries with the name "Hamilton". 
      # Zillow and Remax only has data for the Hamilton city, not the township.
      if item['cityname'] == 'Hamilton' and item['cityType'] == 'Township':
        pass
      else:
        list_cities.append(item['cityname'])
    yield runner.crawl(MortgageRatesSpider)
    yield runner.crawl(OnGovSecSchoolIdSpider)
    yield runner.crawl(OnGovElSchoolIdSpider)
    yield runner.crawl(OnGovSchoolSpider, secSchoolIds=sec_schoolIds_output[0]['schoolIds'], elSchoolIds=el_schoolIds_output[0]['schoolIds'])
    yield runner.crawl(OnGovUniListSpider)
    yield runner.crawl(OnGovUniSpider, university_list=universities)
    yield runner.crawl(OnGovColListSpider)
    yield runner.crawl(OnGovColSpider, college_list=colleges)
    yield runner.crawl(ZillowcaSpider, cities=list_cities)
    yield runner.crawl(AirbnbSpider, cities=list_cities)
    #Note: Yelp doesn't allow web scraping, so to overcome that
    #Yelp Fusion API is used in form of Spider function
    yield runner.crawl(YelpApiSpider, cities=list_cities)
    yield runner.crawl(RemaxSpider, cities=list_cities)
    #Queries the DB to get the coordinates for all the Zillow Listings
    cursor.execute(zillow_coordinates_query)
    zillow_coordinates = cursor.fetchall()
    #Get's the Walkscore for the Zillow Listings
    yield runner.crawl(WalkScoreZillowSpider, listings_coordinates=zillow_coordinates)
    #Queries the DB to get the coordinates for all the Remax Listings
    cursor.execute(remax_coordinates_query)
    remax_coordinates = cursor.fetchall()
    #Get's the Walkscore for the Remax Listings
    yield runner.crawl(WalkScoreRemaxSpider, listings_coordinates=remax_coordinates)
    reactor.stop()
  crawl()
  reactor.run()

if __name__ == '__main__':
  main()
