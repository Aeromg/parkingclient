# -*- coding: utf-8 -*-
__author__ = 'Denis Vesnin, https://github.com/aeromg'

import httplib
import urllib
import json
import datetime
import time
import sys
from threading import Thread
import argparse


def first(iterable):
    for e in iterable:
        return e


class Reservation(object):
    def __init__(self):
        pass

    @property
    def renewed(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def vrp(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def end(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def zone(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def start(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def remaining_second(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def remaining_minutes(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def vehicleType(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def id(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def account(self):
        raise NotImplementedError('Method must be implemented in child class')


class JsonReservation(Reservation):
    def __init__(self, data):
        super(JsonReservation, self).__init__()

        self._data = data

    @property
    def renewed(self):
        return self._data[u'renewed']

    @property
    def vrp(self):
        return self._data[u'vrp']

    @property
    def end(self):
        return datetime.datetime.fromtimestamp(self._data[u'end'] / 1000)

    @property
    def zone(self):
        return self._data[u'zoneNumber']

    @property
    def start(self):
        return datetime.datetime.fromtimestamp(self._data[u'start'] / 1000)

    @property
    def remaining_second(self):
        return self._data[u'remainingTime'] / 1000

    @property
    def remaining_minutes(self):
        return self.remaining_second / 60

    @property
    def vehicleType(self):
        return self._data[u'vehicleType']

    @property
    def id(self):
        return self._data[u'id']

    @property
    def account(self):
        return self._data[u'accountId']


class ParkingClient(object):
    VEHICLE_TYPE_CAR = 'car'

    # VEHICLE_TYPE_BIKE = 'bike'

    def __init__(self):
        pass

    @property
    def account_id(self):
        raise NotImplementedError('Method must be implemented in child class')

    def get_reservations(self):
        raise NotImplementedError('Method must be implemented in child class')

    def renew_reservation(self, reservation, duration):
        assert isinstance(reservation, Reservation)
        raise NotImplementedError('Method must be implemented in child class')

    def stop_reservation(self, reservation):
        assert isinstance(reservation, Reservation)
        raise NotImplementedError('Method must be implemented in child class')

    def start_reservation(self, vehicle, zone, duration, vehicle_type=None):
        raise NotImplementedError('Method must be implemented in child class')

    def get_price(self, zone, vehicle_type):
        raise NotImplementedError('Method must be implemented in child class')

    def get_balance_cent(self):
        raise NotImplementedError('Method must be implemented in child class')

    @property
    def is_login_ok(self):
        raise NotImplementedError('Method must be implemented in child class')

    def login(self):
        raise NotImplementedError('Method must be implemented in child class')


class HttpParkingClient(ParkingClient):
    HOST_NAME = 'permparking.ru'

    URL_LOGIN = '/auth/login'
    URL_USER_INFO = '/api/2.7/accounts/me'
    URL_RESERVATIONS = '/api/2.7/accounts/me/reservations'
    URL_BALANCE = '/api/2.7/accounts/getbalance'
    URL_NOTIFICATIONS = '/api/2.7/accounts/me/settings/notifications'
    URL_RENEW = '/api/2.7/accounts/me/reservations/renew'
    URL_START = '/api/2.7/accounts/me/reservations/start'
    URL_CANCEL = '/api/2.7/accounts/me/reservations/cancel'
    URL_ZONES = '/api/2.7/objects/?types=zones'

    CLIENT_BASE_HEADERS = {
        'Pragma': 'no-cache',
        'Origin': 'https://permparking.ru',
        'Accept-Encoding': 'none',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Cache-Control': 'no-cache',
        'Referer': 'https://permparking.ru',
        'Connection': 'keep-alive'
    }

    class Response(object):
        def __init__(self, headers, body):
            self._headers = dict(headers)
            self._body = body

        @property
        def headers(self):
            return dict(self._headers)

        @property
        def body(self):
            return self._body

    def __init__(self, email, password, connection_retries=1):
        super(HttpParkingClient, self).__init__()

        self._email = email
        self._password = password

        assert connection_retries > 0
        self._connection_retries = connection_retries

        self._is_login_ok = False

        self._cookie = None
        self._user_info_cached = None
        self._zones_cached = None

    def _get_client_headers(self, is_form=False, append=None, is_json=False):
        if append is None:
            append = {}

        if not self._cookie is None:
            append['Cookie'] = self._cookie

        if is_form:
            append['Content-type'] = 'application/x-www-form-urlencoded'

        if is_json:
            append['Content-Type'] = 'application/json'

        headers = HttpParkingClient.CLIENT_BASE_HEADERS.copy()
        headers.update(append)

        return headers

    def _request(self, method, url, is_form=False, params=None, params_json=None, headers=None):
        assert params_json is None or params is None

        data = None

        if params is not None:
            data = urllib.urlencode(params)
        elif params_json is not None:
            data = json.dumps(params_json)

        headers = self._get_client_headers(is_form=is_form, append=headers, is_json=not params_json is None)

        connection = httplib.HTTPSConnection(HttpParkingClient.HOST_NAME)

        retry_countdown = self._connection_retries

        while True:
            retry_countdown -= 1
            try:
                connection.request(method=method,
                                   url=url,
                                   body=data,
                                   headers=headers)
                break
            except Exception, e:
                if retry_countdown == 0:
                    raise e

        http_response = connection.getresponse()

        response = HttpParkingClient.Response(headers=http_response.getheaders(), body=http_response.read())

        http_response.close()
        connection.close()

        return response

    def _get_json(self, url, params_json=None, method='GET'):
        if not self.is_login_ok:
            self.login()

        headers = {
            'Content-Type': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }

        while True:
            http_response = self._request(method=method, url=url, params_json=params_json, headers=headers)
            json_response = json.loads(http_response.body)
            if 'errorName' in json_response.keys():
                if json_response['errorName'] == 'ForbiddenError':
                    self.login()
                    if self.is_login_ok:
                        continue
                    else:
                        raise Exception(json_response['error'])
                else:
                    raise Exception(json_response['error'])

            return json_response

    def renew_reservation(self, reservation, duration):
        if reservation.renewed:
            raise Exception('Already renewed')

        params = {
            'reservationId': reservation.id,
            'duration': duration
        }

        self._get_json(HttpParkingClient.URL_RENEW,
                       params_json=params,
                       method='PUT')

    def stop_reservation(self, reservation):
        assert isinstance(reservation, Reservation)

        params = {
            'reservationId': reservation.id
        }

        return self._get_json(url=HttpParkingClient.URL_CANCEL,
                              params_json=params,
                              method='PUT')

    def start_reservation(self, vehicle, zone, duration, vehicle_type=None):
        assert (isinstance(vehicle, str) or isinstance(vehicle, unicode)) and vehicle
        assert isinstance(zone, int) and (zone > 0)

        if vehicle_type is None:
            vehicle_type = ParkingClient.VEHICLE_TYPE_CAR

        params = {
            'zoneNumber': zone,
            'vrp': vehicle,
            'vehicleType': vehicle_type,
            'duration': duration,
            'accountId': self.account_id
        }

        return self._get_json(url=HttpParkingClient.URL_START,
                              params_json=params,
                              method='PUT')

    def _load_zones(self):
        self._zones_cached = self._get_json(url=HttpParkingClient.URL_ZONES, method='GET')['objects']

    def get_price(self, zone, vehicle_type):
        if self._zones_cached is None:
            self._load_zones()

        for obj in self._zones_cached:
            if obj['number'] == zone:
                for price in obj['prices']:
                    if price['vehicleType'] == vehicle_type:
                        return price['price']

        raise Exception('No zone {0} with vehicle type {1}'.format(zone, vehicle_type))

    @property
    def account_id(self):
        return self._get_user_info()['user']['accountId']

    def _load_user_info(self):
        self._user_info_cached = self._get_json(HttpParkingClient.URL_USER_INFO)['account']

    def _get_user_info(self):
        if self._user_info_cached is None:
            self._load_user_info()

        return self._user_info_cached

    def get_reservations(self):
        return list(map(JsonReservation, self._get_json(HttpParkingClient.URL_RESERVATIONS)['reservations']))

    def get_balance_cent(self):
        params = {
            'accountId': self._get_user_info()['id']
        }

        response = self._get_json(url=HttpParkingClient.URL_BALANCE, params_json=params, method='PUT')

        return response['balance']

    @property
    def is_login_ok(self):
        return self._is_login_ok

    def login(self):
        response = self._request(method='POST',
                                 url=HttpParkingClient.URL_LOGIN,
                                 is_form=True,
                                 params={'email': self._email, 'password': self._password})

        self._is_login_ok = 'location' in response.headers.keys() and '?failed=true' not in response.headers['location']

        if self._is_login_ok:
            self._cookie = response.headers['set-cookie']

        return response


class SMSClient(object):
    HOSTNAME = 'sms.ru'

    RESPONSE_SENT = 100
    RESPONSE_INSUFFICIENT_FOUNDS = 201

    def __init__(self, api_id, testing=False):
        self._api_id = api_id
        self._testing = testing

    def send(self, to, text):
        connection = httplib.HTTPConnection(SMSClient.HOSTNAME)

        params_dict = {
            'api_id': self._api_id,
            'to': to,
            'text': text
        }

        if self._testing:
            params_dict['test'] = 1

        connection.request('GET', url='/sms/send?' + urllib.urlencode(params_dict))
        response = connection.getresponse().read().splitlines()[0]

        connection.close()

        return int(response)


class ParkingMonitor(object):
    __VEHICLE_KEY = 'vehicle'
    __ZONE_KEY = 'zone'
    __REMAIN_KEY = 'remain'
    __REMAIN_MAP_KEY_FORMAT = '{0}/{1}'

    def __init__(self, client):
        assert isinstance(client, ParkingClient)

        self._client = client
        self._observed_vz_map = {}  # vehicle -> list(zone), ...
        self._observed_remain_map = {}  # vehicle/zone -> { vehicle, zone, remain }

        self._new_reservation_handlers = []
        self._remove_reservation_handlers = []
        self._remain_changed_handlers = []

    def add_on_new_reservation_event(self, handler):
        self._new_reservation_handlers.append(handler)

    def add_on_remove_reservation_event(self, handler):
        self._remove_reservation_handlers.append(handler)

    def remove_on_new_reservation_event(self, handler):
        self._new_reservation_handlers.remove(handler)

    def remove_on_remove_reservation_event(self, handler):
        self._remove_reservation_handlers.remove(handler)

    def add_on_remain_changed_event(self, handler):
        self._remain_changed_handlers.append(handler)

    def remove_on_remain_changed_event(self, handler):
        self._remain_changed_handlers.remove(handler)

    def _try_invoke_notify_handlers(self, handlers, *args):
        for handler in handlers:
            try:
                handler(*args)
            except Exception, e:
                sys.stderr.write(repr(e))

    def _on_new_reservation(self, vehicle, zone):
        self._try_invoke_notify_handlers(self._new_reservation_handlers,
                                         vehicle,
                                         zone)

    def _on_remove_reservation(self, vehicle, zone):
        self._try_invoke_notify_handlers(self._remove_reservation_handlers,
                                         vehicle,
                                         zone)

    def _on_remain_change(self, vehicle, zone, remain):
        self._try_invoke_notify_handlers(self._remain_changed_handlers,
                                         vehicle,
                                         zone,
                                         remain)

    def _create_vz_map(self, reservations):
        vz_map = {}

        for vehicle in set([r.vrp for r in reservations]):
            vz_map[vehicle] = set([r.zone for r in reservations if r.vrp == vehicle])

        return vz_map

    def _create_remain_map(self, reservations):
        vzt_map = {}

        for vehicle in set([r.vrp for r in reservations]):
            for zone in set([r.zone for r in reservations if r.vrp == vehicle]):
                vzt_map[ParkingMonitor.__REMAIN_MAP_KEY_FORMAT.format(vehicle, zone)] = {
                    ParkingMonitor.__VEHICLE_KEY: vehicle,
                    ParkingMonitor.__ZONE_KEY: zone,
                    ParkingMonitor.__REMAIN_KEY: max(
                        [r.remaining_minutes for r in reservations if r.vrp == vehicle and r.zone == zone]
                    )
                }

        return vzt_map

    def _apply_vz_map_diff(self, vz_map=None, vz_map_to_insert=None, vz_map_to_remove=None):
        if vz_map is None:
            vz_map = self._observed_vz_map

        if not vz_map_to_insert is None:
            for vehicle in vz_map_to_insert:
                if vehicle not in vz_map.keys():
                    vz_map[vehicle] = vz_map_to_insert[vehicle]
                else:
                    for zone in vz_map_to_insert[vehicle]:
                        if zone not in vz_map[vehicle]:
                            vz_map[vehicle].add(zone)

        if not vz_map_to_remove is None:
            for vehicle in vz_map_to_remove.keys():
                if vehicle in vz_map.keys():
                    for zone in vz_map_to_remove[vehicle]:
                        if zone in vz_map[vehicle]:
                            vz_map[vehicle].remove(zone)

                        if len(vz_map[vehicle]) == 0:
                            del vz_map[vehicle]
                            break

        return vz_map if vz_map != self._observed_vz_map else None

    def _apply_remain_map(self, update, remain_map=None):
        if remain_map is None:
            remain_map = self._observed_remain_map

        remain_map.update(update)

        return remain_map if remain_map != remain_map else None

    def _get_remain_update(self, remain_map):
        update = {}
        observed = self._observed_remain_map

        for key in remain_map.keys():
            remain = remain_map[key][ParkingMonitor.__REMAIN_KEY]

            if key not in observed.keys() or observed[key][ParkingMonitor.__REMAIN_KEY] != remain:
                update[key] = remain_map[key].copy()

        return update

    def _get_vz_map_diff(self, old_map, new_map):
        assert isinstance(old_map, dict)
        assert isinstance(new_map, dict)

        diff_vz_map = {}

        old_vehicles = old_map.keys()

        for new_vehicle in new_map.keys():
            if new_vehicle not in old_vehicles:
                diff_vz_map[new_vehicle] = set(new_map[new_vehicle])
            else:
                diff = list(old_map[new_vehicle] - new_map[new_vehicle])
                if len(diff):
                    diff_vz_map[new_vehicle] = diff

        return diff_vz_map

    def _get_new_vz_map(self, reservation_vz_map):
        return self._get_vz_map_diff(old_map=self._observed_vz_map,
                                     new_map=reservation_vz_map)

    def _get_removed_vz_map(self, reservation_vz_map):
        return self._get_vz_map_diff(old_map=reservation_vz_map,
                                     new_map=self._observed_vz_map)

    def _visit_vz_map(self, vz_map, func):
        for vehicle in vz_map.keys():
            for zone in vz_map[vehicle]:
                func(vehicle=vehicle, zone=zone)

    def _visit_remain_map(self, remain_map, func):
        for key in remain_map.keys():
            element = remain_map[key]
            func(
                vehicle=element[ParkingMonitor.__VEHICLE_KEY],
                zone=element[ParkingMonitor.__ZONE_KEY],
                remain=element[ParkingMonitor.__REMAIN_KEY]
            )

    def _clean_remain_map(self, reservations):
        keys = self._observed_remain_map.keys()
        for reservation in reservations:
            key = ParkingMonitor.__REMAIN_MAP_KEY_FORMAT.format(reservation.vrp, reservation.zone)
            if key not in keys:
                del self._observed_remain_map[key]

    def measure_one_shot(self):
        reservations = self._client.get_reservations()
        reservation_vz_map = self._create_vz_map(reservations=reservations)
        remain_map = self._create_remain_map(reservations=reservations)

        # changes
        new_vz_map = self._get_new_vz_map(reservation_vz_map)
        removed_vz_map = self._get_removed_vz_map(reservation_vz_map)

        self._visit_vz_map(new_vz_map, self._on_new_reservation)
        self._visit_vz_map(removed_vz_map, self._on_remove_reservation)

        self._apply_vz_map_diff(vz_map_to_insert=new_vz_map, vz_map_to_remove=removed_vz_map)

        # time tick
        remain_update = self._get_remain_update(remain_map)

        self._visit_remain_map(remain_update, self._on_remain_change)

        self._apply_remain_map(remain_update)
        self._clean_remain_map(reservations)

        return reservations


class NotifyBackend(object):
    def __init__(self, notify_filter=None):
        pass


class TextNotifyBackend(NotifyBackend):
    def __init__(self, formatter, notify_filter=None):
        super(TextNotifyBackend, self).__init__(notify_filter=notify_filter)

        assert isinstance(formatter, NotifyMessageFormatter)
        self._formatter = formatter

    def new_reservation(self, vehicle, zone):
        self.send_virtual(self._formatter.get_new_reservation_message(vehicle=vehicle, zone=zone))

    def send_virtual(self, text):
        raise NotImplementedError('Method must be implemented in child class')


class UnixPipeNotifyBackend(NotifyBackend):
    def __init__(self, pipe, timestamp=False):
        super(UnixPipeNotifyBackend, self).__init__()

        self._pipe = pipe
        self._timestamp = timestamp

    def send(self, text):
        if self._timestamp:
            self._pipe.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            self._pipe.write(' ')
        self._pipe.write(text)
        self._pipe.write('\n')
        self._pipe.flush()


class SMSNotifyBackend(NotifyBackend):
    def __init__(self, sms_client, recipients):
        super(SMSNotifyBackend, self).__init__()

        assert isinstance(sms_client, SMSClient)
        assert isinstance(recipients, list)
        assert all([isinstance(recipient, str) or isinstance(recipient, unicode) for recipient in recipients])

        self._sms_client = sms_client
        self._recipients = recipients

    def send(self, text):
        for recipient in self._recipients:
            self._sms_client.send(to=recipient, text=text)


class NotifyMessageFormatter(object):
    def __init__(self):
        pass

    def get_new_reservation_message(self, vehicle, zone):
        raise NotImplementedError('Method must be implemented in child class')

    def get_remove_reservation_message(self, vehicle, zone):
        raise NotImplementedError('Method must be implemented in child class')

    def get_remain_message(self, vehicle, zone, remain):
        raise NotImplementedError('Method must be implemented in child class')


class NotifyFormatterRussian(NotifyMessageFormatter):
    def __init__(self):
        super(NotifyFormatterRussian, self).__init__()

    def _format_word(self, number, w5to10, w1, w2to4):
        mod = number % 10

        if 5 <= number < 20 or mod == 0 or 5 <= mod <= 9:
            return w5to10

        if mod == 1:
            return w1

        if 2 <= mod <= 4:
            return w2to4

        return w5to10

    def _format_hour(self, number):
        return self._format_word(number, 'часов', 'час', 'часа')

    def _format_minute(self, number):
        return self._format_word(number, 'минут', 'минута', 'минуты')

    def _get_hour_minute_tuple(self, minutes):
        return minutes / 60, minutes % 60

    def get_new_reservation_message(self, vehicle, zone):
        return 'Тачка {0} в зоне {1} припаркована.'.format(vehicle, zone)

    def get_remove_reservation_message(self, vehicle, zone):
        return 'Кончилась парковка {0} в зоне {1}.'.format(vehicle, zone)

    def get_remain_message(self, vehicle, zone, remain):
        hour, minutes = self._get_hour_minute_tuple(remain)

        if hour > 0:
            remain_word = self._format_word(hour, 'Осталось', 'Остался', 'Осталось')
            if minutes > 0:
                remain_msg = '{0} {1} и {2} {3}'.format(hour, self._format_hour(hour),
                                                        minutes, self._format_minute(minutes))
            else:
                remain_msg = '{0} {1}'.format(hour, self._format_hour(hour))
        else:
            remain_word = self._format_word(minutes, 'Осталось', 'Осталась', 'Осталось')
            remain_msg = '{0} {1}'.format(minutes, self._format_minute(minutes))

        return '{0} {1} парковки {2} в зоне {3}.'.format(remain_word, remain_msg, vehicle, zone)


class NotifyFilter(object):
    def __init__(self):
        pass

    def new_reservation_filter(self, vehicle, zone):
        return True

    def remove_reservation_filter(self, vehicle, zone):
        return True

    def remain_filter(self, vehicle, zone, remain):
        return True


class SimpleNotifyFilter(NotifyFilter):
    def __init__(self, deny_new=False, deny_remove=False, deny_remain=False):
        super(SimpleNotifyFilter, self).__init__()

        self._deny_new = deny_new
        self._deny_remove = deny_remove
        self._deny_remain = deny_remain

    def new_reservation_filter(self, vehicle, zone):
        return not self._deny_new

    def remove_reservation_filter(self, vehicle, zone):
        return not self._deny_remove

    def remain_filter(self, vehicle, zone, remain):
        return not self._deny_remain


class RemainStageNotifyFilter(NotifyFilter):
    def __init__(self):
        super(RemainStageNotifyFilter, self).__init__()

        self._stages = set()
        self._remain_sent = {}
        self._last_remain = {}

    def _get_vz_key(self, vehicle, zone):
        return '{0}/{1}'.format(vehicle, zone)

    def _try_get_dict_value(self, vehicle, zone, dictionary, default):
        key = self._get_vz_key(vehicle=vehicle, zone=zone)
        return dictionary[key] if key in dictionary.keys() else default

    def _set_dict_value(self, vehicle, zone, dictionary, value):
        key = self._get_vz_key(vehicle=vehicle, zone=zone)
        if not value is None:
            dictionary[key] = value
        else:
            if key in dictionary.keys():
                del dictionary[key]

        self.clean()

    def _get_last_remain_sent(self, vehicle, zone):
        return self._try_get_dict_value(vehicle=vehicle, zone=zone, dictionary=self._remain_sent, default=sys.maxint)

    def _get_last_remain(self, vehicle, zone):
        return self._try_get_dict_value(vehicle=vehicle, zone=zone, dictionary=self._remain_sent, default=-1)

    def _set_last_remain_sent(self, vehicle, zone, remain):
        self._set_dict_value(vehicle=vehicle, zone=zone, dictionary=self._remain_sent, value=remain)

    def _reset_last_remain_sent(self, vehicle, zone):
        self._set_last_remain_sent(vehicle=vehicle, zone=zone, remain=None)

    def _set_last_remain(self, vehicle, zone, remain):
        self._set_dict_value(vehicle=vehicle, zone=zone, dictionary=self._last_remain, value=remain)

    def clean(self):
        for key in self._remain_sent.keys():
            if self._remain_sent[key] == 0:
                del self._remain_sent[key]

    def add_remain_stage(self, remain):
        self._stages.add(remain)

    def remove_remain_stage(self, remain):
        if remain in self._stages:
            self._stages.remove(remain)

    def remain_filter(self, vehicle, zone, remain):
        if len(self._stages) == 0:
            return True

        if remain > self._get_last_remain(vehicle=vehicle, zone=zone):
            self._reset_last_remain_sent(vehicle=vehicle, zone=zone)

        self._set_last_remain(vehicle=vehicle, zone=zone, remain=remain)

        last_remain = self._get_last_remain_sent(vehicle=vehicle, zone=zone)
        passed = False

        for stage in sorted(self._stages, reverse=True):
            if remain <= stage:
                if last_remain > stage:
                    self._set_last_remain_sent(vehicle=vehicle, zone=zone, remain=stage)
                    passed = True

        return passed


class ParkingMonitorNotifier(object):
    def __init__(self, monitor, notify_backend, formatter,
                 message_filter=None, update_interval=30.0, idle_update_interval=None):

        if not isinstance(notify_backend, list):
            notify_backend_list = [notify_backend, ]
        else:
            notify_backend_list = list(notify_backend)

        if message_filter is None:
            message_filter_list = []
        else:
            message_filter_list = list(message_filter)

        assert isinstance(monitor, ParkingMonitor)
        assert all([isinstance(e, NotifyBackend) for e in notify_backend_list])
        assert all([isinstance(e, NotifyFilter) for e in message_filter_list])
        assert isinstance(formatter, NotifyMessageFormatter)
        assert (isinstance(update_interval, int) or isinstance(update_interval, float)) and update_interval > 0
        assert idle_update_interval is None or (isinstance(idle_update_interval, int) and idle_update_interval > 0)

        self._monitor = monitor
        self._notify_backend = notify_backend_list
        self._message_filter = message_filter_list
        self._formatter = formatter
        self._update_interval = update_interval
        self._idle_update_interval = update_interval * 2.0 if idle_update_interval is None else idle_update_interval

        self._run_flag = False

    def _notify_send(self, text):
        for backend in self.notify_backend:
            backend.send(text=text)

    def _on_new_reservation(self, vehicle, zone):
        for message_filter in self._message_filter:
            if not message_filter.new_reservation_filter(vehicle=vehicle, zone=zone):
                return

        self._notify_send(self._formatter.get_new_reservation_message(vehicle=vehicle,
                                                                      zone=zone))

    def _on_remove_reservation(self, vehicle, zone):
        for message_filter in self._message_filter:
            if not message_filter.remove_reservation_filter(vehicle=vehicle, zone=zone):
                return

        self._notify_send(self._formatter.get_remove_reservation_message(vehicle=vehicle,
                                                                         zone=zone))

    def _on_reservation_remain_change(self, vehicle, zone, remain):
        for message_filter in self._message_filter:
            if not message_filter.remain_filter(vehicle=vehicle, zone=zone, remain=remain):
                return

        self._notify_send(self._formatter.get_remain_message(vehicle=vehicle,
                                                             zone=zone,
                                                             remain=remain))

    def _subscribe_monitor_events(self):
        self._monitor.add_on_new_reservation_event(self._on_new_reservation)
        self._monitor.add_on_remove_reservation_event(self._on_remove_reservation)
        self._monitor.add_on_remain_changed_event(self._on_reservation_remain_change)

    def _remove_monitor_events(self):
        self._monitor.remove_on_new_reservation_event(self._on_new_reservation)
        self._monitor.remove_on_remove_reservation_event(self._on_remove_reservation)
        self._monitor.remove_on_remove_reservation_event(self._on_reservation_remain_change)

    @property
    def notify_backend(self):
        return self._notify_backend

    def stop(self):
        self._run_flag = False
        self._remove_monitor_events()

    def run(self):
        self._run_flag = True
        self._subscribe_monitor_events()

        while self._run_flag:
            try:
                reservations = self._monitor.measure_one_shot()
                time.sleep(self._update_interval if len(reservations) > 0 else self._idle_update_interval)
            except Exception, e:
                sys.stderr.write(repr(e))
                sys.stderr.write('\n')


def wait_and_start_reservation(client, vehicle, zone, duration, wait):
    assert isinstance(client, ParkingClient)

    time.sleep(wait)
    retries_remain = 16
    while True:
        try:
            client.start_reservation(vehicle=vehicle, zone=zone, duration=duration)
            break
        except Exception, e:
            sys.stderr.write(repr(e))
            sys.stderr.write('\n')
            retries_remain -= 1
            if retries_remain > 0:
                sys.stderr.write(repr(e))
                sys.stderr.write('\n')
                time.sleep(1)
                continue
            else:
                raise e

    print('Хитрое продление {0} в зоне {1} на {2} мин. :)'.format(vehicle, zone, duration))
    print('Осталось {0} денег.'.format(client.get_balance_cent() / 100))


if __name__ == '__main__':
    jew_auto_renew = True  # хитрое продление
    start_now = True  # начать прямо сейчас
    user_email = 'example@domain.tld'
    user_password = 'password'
    sms_ru_api_id = 'place_your_developer_id_here'
    sms_ru_recipient_phone = '79221111111'
    sms_enabled = False

    parking_client = HttpParkingClient(user_email, user_password, connection_retries=8)
    parking_monitor = ParkingMonitor(client=parking_client)
    sms_client = SMSClient(api_id=sms_ru_api_id, testing=False)
    sms_notify_backend = SMSNotifyBackend(sms_client=sms_client, recipients=[sms_ru_recipient_phone, ])
    messages_formatter = NotifyFormatterRussian()
    stdout_notify_backend = UnixPipeNotifyBackend(pipe=sys.stdout, timestamp=True)
    remain_filter = RemainStageNotifyFilter()
    deny_new_reservation_notify_filter = SimpleNotifyFilter(deny_new=True)

    # напоминалки об окончании
    # за 5 минут
    remain_filter.add_remain_stage(5)

    # за 30 минут
    remain_filter.add_remain_stage(30)

    # за час
    remain_filter.add_remain_stage(60)

    if jew_auto_renew:
        on_reservation_ends = lambda v, z: Thread(target=wait_and_start_reservation,
                                                  args=(parking_client, v, z, 60, 60 * 10)).start()

        parking_monitor.add_on_remove_reservation_event(on_reservation_ends)

    notifiers = [stdout_notify_backend, sms_notify_backend] if sms_enabled else [stdout_notify_backend, ]
    monitor_notifier = ParkingMonitorNotifier(monitor=parking_monitor,
                                              notify_backend=notifiers,
                                              formatter=messages_formatter,
                                              message_filter=[remain_filter, deny_new_reservation_notify_filter],
                                              update_interval=32)

    if start_now:
        parking_client.start_reservation(vehicle='А123ВЕ59', zone=101, duration=60)

    monitor_notifier.run()
