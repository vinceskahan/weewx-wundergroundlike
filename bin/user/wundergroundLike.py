#-------------------------------------------------------------
#         custom WundergroundLike uploader
#
#    Copyright (c) 2025 Vince Skahan <vinceskahan@gmail.com>
#
# This is derived almost verbatim from weewx 5.2.0 restx.py 
# which is:
#
#    Copyright (c) 2009-2024 Tom Keffer <tkeffer@gmail.com>
#
# The upstream code this is based on uses a LICENSE.txt file
# that is present here for reference.
#
#-------------------------------------------------------------

import datetime
import http.client
import logging
import platform
import queue
import random
import re
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import weedb
import weeutil.logger
import weeutil.weeutil
import weewx.engine
import weewx.manager
import weewx.units
from weeutil.config import search_up, accumulateLeaves
from weeutil.weeutil import to_int, to_float, to_bool, timestamp_to_string, to_sorted_string

log = logging.getLogger(__name__)


class FailedPost(Exception):
    """Raised when a post fails, and is unlikely to succeed if retried."""


class AbortedPost(Exception):
    """Raised when a post is aborted by the client."""


class BadLogin(Exception):
    """Raised when login information is bad or missing."""


class ConnectError(IOError):
    """Raised when unable to get a socket connection."""


class SendError(IOError):
    """Raised when unable to send through a socket."""

#------------------------------------------------------
#         custom WundergroundLike uploader
#------------------------------------------------------

class WundergroundLike(weewx.restx.StdWunderground):

    """Customized version of the Ambient protocol for the Weather Underground,
       intended to support sites that use WU protocols, yet use different URLs
       for uploading.  Consult weewx's restx.py for commentary on the various defaults
       and features therein.

       Differences from the weewx Wunderground class:
         - set default URLs to bogus values
         - supersede pws_url with mandatory'server_url' from [[WundergroundLike]] 
         - explicitly point to weewx.restx.foo for a few items
         - slightly different logging output to reflect this class's name
         - slightly different/added logging 
         - rapidfire is hard-coded to be False
    """

    # the rapidfire URL:
    rf_url = "http://localhost/rf_url_undefined"
    # the personal weather station URL:
    pws_url = "http://localhost/pws_url_undefined"

    def __init__(self, engine, config_dict):

        super().__init__(engine, config_dict)

        _ambient_dict = weewx.restx.get_site_dict(
            config_dict, 'WundergroundLike', 'station', 'password', 'server_url')
        if _ambient_dict is None:
            return
        else:
            log.info("_ambient_dict: ", _ambient_dict)

        # force rapidfire false
        _ambient_dict['rapidfire'] = False

        # supersede default pws_url used in WU with server_url from weewx.conf
        pws_url = _ambient_dict['server_url']
        log.debug("WundergroundLike server_url: %s", pws_url)

        _essentials_dict = search_up(config_dict['StdRESTful']['Wunderground'], 'Essentials', {})

        log.debug("WU essentials: %s", _essentials_dict)

        # Get the manager dictionary:
        _manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding')

        # The default is to not do an archive post if a rapidfire post
        # has been specified, but this can be overridden
        do_rapidfire_post = to_bool(_ambient_dict.pop('rapidfire', False))
        do_archive_post = to_bool(_ambient_dict.pop('archive_post',
                                                    not do_rapidfire_post))
        if do_archive_post:
            _ambient_dict.setdefault('server_url', WundergroundLike.pws_url)
            self.archive_queue = queue.Queue()
            self.archive_thread = weewx.restx.AmbientThread(
                self.archive_queue,
                _manager_dict,
                protocol_name="WundergroundLike",
                essentials=_essentials_dict,
                **_ambient_dict)
            self.archive_thread.start()
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            log.info("WundergroundLike: Data for station %s will be posted",
                     _ambient_dict['station'])

        if do_rapidfire_post:
            _ambient_dict.setdefault('server_url', weewx.restx.StdWunderground.rf_url)
            _ambient_dict.setdefault('log_success', False)
            _ambient_dict.setdefault('log_failure', False)
            _ambient_dict.setdefault('max_backlog', 0)
            _ambient_dict.setdefault('max_tries', 1)
            _ambient_dict.setdefault('rtfreq', 2.5)
            self.cached_values = CachedValues()
            self.loop_queue = queue.Queue()
            self.loop_thread = weewx.restx.AmbientLoopThread(
                self.loop_queue,
                _manager_dict,
                protocol_name="Wunderground-RF",
                essentials=_essentials_dict,
                **_ambient_dict)
            self.loop_thread.start()
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            log.info("WundergroundLike-RF: Data for station %s will be posted",
                     _ambient_dict['station'])

    def new_loop_packet(self, event):
        """Puts new LOOP packets in the loop queue"""
        if weewx.debug >= 3:
            log.debug("Raw packet: %s", to_sorted_string(event.packet))
        self.cached_values.update(event.packet, event.packet['dateTime'])
        if weewx.debug >= 3:
            log.debug("Cached packet: %s",
                      to_sorted_string(self.cached_values.get_packet(event.packet['dateTime'])))
        self.loop_queue.put(
            self.cached_values.get_packet(event.packet['dateTime']))

    def new_archive_record(self, event):
        """Puts new archive records in the archive queue"""
        self.archive_queue.put(event.record)


