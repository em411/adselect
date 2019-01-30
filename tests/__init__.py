import json
import socket
from collections import defaultdict
from copy import deepcopy

import txmongo
from mock import MagicMock
from twisted.internet import defer, reactor
from twisted.internet.defer import succeed
from twisted.internet.protocol import Protocol
from twisted.trial import unittest
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from zope.interface import implements

from adselect import db as adselect_db
from adselect.db import utils as db_utils
from adselect.iface import const as iface_consts, protocol as iface_proto, server as iface_server, utils as iface_utils
from adselect.stats import cache as stats_cache


class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class ReceiverProtocol(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.body = []

    def dataReceived(self, databytes):
        self.body.append(databytes)

    def connectionLost(self, reason):
        self.finished.callback(''.join(self.body))


class DataTestCase(unittest.TestCase):
    _campaigns = [{'time_start': 1024765751, 'campaign_id': 'c_Marci', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Rusty': 'Max', 'Malaclypse': 'Jin', 'Wendi': 'Kimberly', 'Sidney': 'Jane',
                                'Blair': 'Hans', 'Ravindran': 'Sekar'},
                   'banners': [{'keywords': {'Carolyn': 'Lyndon'}, 'banner_id': 'b_Juri', 'banner_size': '10x10'},
                               {'keywords': {'Sidney': 'Jane'}, 'banner_id': 'b_Shirley', 'banner_size': '25x25'},
                               {'keywords': {'Santa': 'Malaclypse'}, 'banner_id': 'b_Jan', 'banner_size': '50x50'}]},
                  {'time_start': 1024765751, 'campaign_id': 'c_Ti', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Rusty': 'Max', 'Santa': 'Malaclypse', 'Sidney': 'Jane', 'Malaclypse': 'Jin',
                                'Jeffrey': 'Victoria', 'Saiid': 'Liber'},
                   'banners': [{'keywords': {'Ravindran': 'Sekar'}, 'banner_id': 'b_Sabrina', 'banner_size': '96x96'},
                               {'keywords': {'Ravindran': 'Sekar'}, 'banner_id': 'b_Jeffrey', 'banner_size': '16x16'},
                               {'keywords': {'Wendi': 'Kimberly'}, 'banner_id': 'b_Laurent', 'banner_size': '93x93'}]},
                  {'time_start': 1024765751, 'campaign_id': 'c_Dieter', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Sidney': 'Jane', 'Rusty': 'Max', 'Santa': 'Malaclypse', 'Wendi': 'Kimberly',
                                'Ravindran': 'Sekar', 'Saiid': 'Liber'},
                   'banners': [{'keywords': {'Malaclypse': 'Jin'}, 'banner_id': 'b_Melinda', 'banner_size': '16x16'},
                               {'keywords': {'Blair': 'Hans'}, 'banner_id': 'b_Vincenzo', 'banner_size': '20x20'},
                               {'keywords': {'Sidney': 'Jane'}, 'banner_id': 'b_Roxanne', 'banner_size': '48x48'}]},
                  {'time_start': 1024765751, 'campaign_id': 'c_Johann', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Rusty': 'Max', 'Sidney': 'Jane', 'Santa': 'Malaclypse', 'Malaclypse': 'Jin',
                                'Jeffrey': 'Victoria', 'Saiid': 'Liber'},
                   'banners': [{'keywords': {'Sidney': 'Jane'}, 'banner_id': 'b_Nicolette', 'banner_size': '54x54'},
                               {'keywords': {'Sidney': 'Jane'}, 'banner_id': 'b_Claudia', 'banner_size': '32x32'},
                               {'keywords': {'Santa': 'Malaclypse'}, 'banner_id': 'b_Barrio', 'banner_size': '66x66'}]},
                  {'time_start': 1024765751, 'campaign_id': 'c_Annard', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Sidney': 'Jane', 'Wendi': 'Kimberly', 'Saiid': 'Liber', 'Blair': 'Hans',
                                'Ravindran': 'Sekar', 'Carolyn': 'Lyndon'},
                   'banners': [{'keywords': {'Carolyn': 'Lyndon'}, 'banner_id': 'b_Matthias', 'banner_size': '21x21'},
                               {'keywords': {'Malaclypse': 'Jin'}, 'banner_id': 'b_Boyce', 'banner_size': '51x51'},
                               {'keywords': {'Carolyn': 'Lyndon'}, 'banner_id': 'b_Pradeep', 'banner_size': '56x56'}]},
                  {'time_start': 1024765751, 'campaign_id': 'c_Malloy', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Carolyn': 'Lyndon', 'Sidney': 'Jane', 'Santa': 'Malaclypse', 'Malaclypse': 'Jin',
                                'Wendi': 'Kimberly', 'Saiid': 'Liber'},
                   'banners': [{'keywords': {'Ravindran': 'Sekar'}, 'banner_id': 'b_Jacob', 'banner_size': '36x36'},
                               {'keywords': {'Jeffrey': 'Victoria'}, 'banner_id': 'b_Elisabeth',
                                'banner_size': '60x60'},
                               {'keywords': {'Ravindran': 'Sekar'}, 'banner_id': 'b_Connie', 'banner_size': '22x22'}]},
                  {'time_start': 1024765751, 'campaign_id': 'c_Holly', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Jeffrey': 'Victoria', 'Carolyn': 'Lyndon', 'Sidney': 'Jane', 'Malaclypse': 'Jin',
                                'Ravindran': 'Sekar', 'Saiid': 'Liber'},
                   'banners': [{'keywords': {'Malaclypse': 'Jin'}, 'banner_id': 'b_Harv', 'banner_size': '91x91'},
                               {'keywords': {'Blair': 'Hans'}, 'banner_id': 'b_Shean', 'banner_size': '46x46'},
                               {'keywords': {'Wendi': 'Kimberly'}, 'banner_id': 'b_Anderson', 'banner_size': '63x63'}]},
                  {'time_start': 1024765751, 'campaign_id': 'c_Martha', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Sidney': 'Jane', 'Jeffrey': 'Victoria', 'Wendi': 'Kimberly', 'Santa': 'Malaclypse',
                                'Malaclypse': 'Jin', 'Saiid': 'Liber'},
                   'banners': [{'keywords': {'Blair': 'Hans'}, 'banner_id': 'b_Rand', 'banner_size': '52x52'},
                               {'keywords': {'Ravindran': 'Sekar'}, 'banner_id': 'b_Loukas', 'banner_size': '61x61'},
                               {'keywords': {'Saiid': 'Liber'}, 'banner_id': 'b_Catherine', 'banner_size': '73x73'}]},
                  {'time_start': 1024765751, 'campaign_id': 'c_Mara', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Rusty': 'Max', 'Carolyn': 'Lyndon', 'Sidney': 'Jane', 'Malaclypse': 'Jin',
                                'Ravindran': 'Sekar', 'Jeffrey': 'Victoria'},
                   'banners': [{'keywords': {'Ravindran': 'Sekar'}, 'banner_id': 'b_Ernie', 'banner_size': '64x64'},
                               {'keywords': {'Santa': 'Malaclypse'}, 'banner_id': 'b_Ahmed', 'banner_size': '97x97'},
                               {'keywords': {'Wendi': 'Kimberly'}, 'banner_id': 'b_Greg', 'banner_size': '21x21'}]},
                  {'time_start': 1024765751, 'campaign_id': 'c_Emmett', 'time_end': 2024765751,
                   'filters': {'exclude': {},
                               'require': {}},
                   'keywords': {'Rusty': 'Max', 'Sidney': 'Jane', 'Santa': 'Malaclypse', 'Malaclypse': 'Jin',
                                'Wendi': 'Kimberly', 'Carolyn': 'Lyndon'},
                   'banners': [{'keywords': {'Rusty': 'Max'}, 'banner_id': 'b_Anatoly', 'banner_size': '84x84'},
                               {'keywords': {'Carolyn': 'Lyndon'}, 'banner_id': 'b_Pratapwant', 'banner_size': '72x72'},
                               {'keywords': {'Wendi': 'Kimberly'}, 'banner_id': 'b_Donal', 'banner_size': '93x93'}]}]
    _impressions = [{'keywords': {'Rusty': 'Max', 'Jeffrey': 'Victoria', 'Blair': 'Hans', 'Ravindran': 'Sekar',
                                  'Carolyn': 'Lyndon'},
                     'user_id': 'user_Gregory',
                     'banner_id': 'b_Juri',
                     'event_id': 'f2801f1b9fd1',
                     'publisher_id': 'pub_Ellen',
                     'paid_amount': 17}, {
                        'keywords': {'Rusty': 'Max', 'Blair': 'Hans', 'Carolyn': 'Lyndon', 'Santa': 'Malaclypse',
                                     'Saiid': 'Liber'}, 'user_id': 'user_Guy', 'banner_id': 'b_Shirley',
                        'event_id': '3a216d1b676e',
                        'publisher_id': 'pub_Ellen', 'paid_amount': 55}, {
                        'keywords': {'Rusty': 'Max', 'Blair': 'Hans', 'Ravindran': 'Sekar', 'Santa': 'Malaclypse',
                                     'Saiid': 'Liber'}, 'user_id': 'user_Gregory', 'banner_id': 'b_Jan',
                        'event_id': '53ab88618666',
                        'publisher_id': 'pub_Ellen', 'paid_amount': 77}, {
                        'keywords': {'Rusty': 'Max', 'Sidney': 'Jane', 'Malaclypse': 'Jin', 'Wendi': 'Kimberly',
                                     'Santa': 'Malaclypse'}, 'user_id': 'user_Aimee', 'banner_id': 'b_Sabrina',
                        'event_id': '10b4e37b9895',
                        'publisher_id': 'pub_Tovah', 'paid_amount': 21}, {
                        'keywords': {'Malaclypse': 'Jin', 'Ravindran': 'Sekar', 'Carolyn': 'Lyndon', 'Blair': 'Hans',
                                     'Saiid': 'Liber'}, 'user_id': 'user_Earle', 'banner_id': 'b_Jeffrey',
                        'event_id': '811af068fb48',
                        'publisher_id': 'pub_Lee', 'paid_amount': 47}, {
                        'keywords': {'Rusty': 'Max', 'Blair': 'Hans', 'Wendi': 'Kimberly', 'Santa': 'Malaclypse',
                                     'Saiid': 'Liber'}, 'user_id': 'user_Earle', 'banner_id': 'b_Laurent',
                        'event_id': '770f99705e55',
                        'publisher_id': 'pub_Jared', 'paid_amount': 38}, {
                        'keywords': {'Rusty': 'Max', 'Malaclypse': 'Jin', 'Ravindran': 'Sekar', 'Sidney': 'Jane',
                                     'Santa': 'Malaclypse'}, 'user_id': 'user_Gregory', 'banner_id': 'b_Melinda',
                        'event_id': '4d0d606d9b66',
                        'publisher_id': 'pub_Lee', 'paid_amount': 61}, {
                        'keywords': {'Rusty': 'Max', 'Carolyn': 'Lyndon', 'Sidney': 'Jane', 'Santa': 'Malaclypse',
                                     'Saiid': 'Liber'}, 'user_id': 'user_Gregory', 'banner_id': 'b_Vincenzo',
                        'event_id': '6a030c297651',
                        'publisher_id': 'pub_Ellen', 'paid_amount': 49}, {
                        'keywords': {'Jeffrey': 'Victoria', 'Rusty': 'Max', 'Wendi': 'Kimberly', 'Sidney': 'Jane',
                                     'Saiid': 'Liber'}, 'user_id': 'user_Gregory', 'banner_id': 'b_Roxanne',
                        'event_id': '1bbb6395356f',
                        'publisher_id': 'pub_Sanjib', 'paid_amount': 93}, {
                        'keywords': {'Blair': 'Hans', 'Ravindran': 'Sekar', 'Sidney': 'Jane', 'Wendi': 'Kimberly',
                                     'Saiid': 'Liber'}, 'user_id': 'user_Gregory', 'banner_id': 'b_Nicolette',
                        'event_id': 'c232b08395ca',
                        'publisher_id': 'pub_Jared', 'paid_amount': 73}]

    def load_campaigns(self):
        for campaign in self.campaigns:
            db_utils.update_campaign(campaign)

            for banner in campaign['banners']:
                banner['campaign_id'] = campaign['campaign_id']
                yield db_utils.update_banner(banner)

    @defer.inlineCallbacks
    def load_campaign_objects(self):

        for campaign in self.campaigns:

            campaign['filters'] = iface_proto.RequireExcludeObject(require=campaign['filters']['require'],
                                                                   exclude=campaign['filters']['exclude'])

            campaign['banners'] = [iface_proto.BannerObject(campaign_id=campaign['campaign_id'], **b) for b in campaign['banners']]

            yield iface_utils.create_or_update_campaign(iface_proto.CampaignObject(**campaign))


class DBTestCase(DataTestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.campaigns = deepcopy(self._campaigns)
        self.impressions = deepcopy(self._impressions)

        self.conn = yield adselect_db.get_mongo_connection()
        self.db = yield adselect_db.get_mongo_db()

        yield adselect_db.configure_db()
        self.timeout = 5

    @defer.inlineCallbacks
    def tearDown(self):
        if adselect_db.MONGO_CONNECTION:
            yield self.conn.drop_database(self.db)
        yield adselect_db.disconnect()


class WebTestCase(DBTestCase):

    @defer.inlineCallbacks
    def setUp(self):
        yield super(WebTestCase, self).setUp()

        self.port = iface_server.configure_iface()
        self.client = Agent(reactor)

        host = socket.gethostbyname(socket.gethostname())
        self.url = 'http://{0}:{1}'.format(host, iface_consts.SERVER_PORT)

    @defer.inlineCallbacks
    def tearDown(self):
        yield super(WebTestCase, self).tearDown()

        self.port.stopListening()

    @defer.inlineCallbacks
    def get_response(self, method, params=None):
        post_data = StringProducer(json.dumps({
            "jsonrpc": "2.0",
            "id": "test_hit",
            "method": method,
            "params": params
        }))

        response = yield self.client.request('POST',
                                             self.url,
                                             Headers({'content-type': ['application/json']}),
                                             post_data)

        finished = defer.Deferred()
        response.deliverBody(ReceiverProtocol(finished))
        data = yield finished
        defer.returnValue(json.loads(data) if data else None)


try:
    import mongomock

    class MongoMockTestCase(DataTestCase):

        def setUp(self):

            stats_cache.BEST_KEYWORDS = defaultdict(lambda: defaultdict(list))
            stats_cache.KEYWORDS_BANNERS = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
            stats_cache.BANNERS = defaultdict(list)
            stats_cache.KEYWORD_IMPRESSION_PAID_AMOUNT = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: float(0.0))))
            stats_cache.IMPRESSIONS_COUNT = defaultdict(lambda: defaultdict(lambda: int(0)))

            self.campaigns = deepcopy(self._campaigns)
            self.impressions = deepcopy(self._impressions)

            adselect_db.MONGO_CONNECTION = None

            self.connection = mongomock.MongoClient()
            self.connection.disconnect = MagicMock()
            self.connection.disconnect.return_value = True

            self.mock_lazyMongoConnectionPool = MagicMock()
            self.mock_lazyMongoConnectionPool.return_value = self.connection
            self.patch(txmongo, 'lazyMongoConnectionPool', self.mock_lazyMongoConnectionPool)

            def mock_create_index(obj, index, *args, **kwargs):
                obj.old_create_index([i[1][0] for i in index.items()], *args, **kwargs)

            mongomock.Collection.old_create_index = mongomock.Collection.create_index
            mongomock.Collection.create_index = mock_create_index

            def mock_find(obj, *args, **kwargs):
                with_cursor = False
                if 'cursor' in kwargs.keys():
                    with_cursor = True
                    del kwargs['cursor']

                cursor = obj.old_find(*args, **kwargs)

                if with_cursor:
                    return [d for d in cursor], ([], None)
                else:
                    return [d for d in cursor]

            mongomock.Collection.old_find = mongomock.Collection.find
            mongomock.Collection.find = mock_find

            def mock_find_one(obj, *args, **kwargs):
                kwargs['limit'] = 1
                cursor = obj.old_find(*args, **kwargs)
                if cursor.count() > 0:
                    return cursor[0]
                return None

            mongomock.Collection.find_one = mock_find_one

        def tearDown(self):
            mongomock.Collection.create_index = mongomock.Collection.old_create_index
            mongomock.Collection.find = mongomock.Collection.old_find

    db_test_case = MongoMockTestCase
except ImportError:
    db_test_case = DBTestCase
