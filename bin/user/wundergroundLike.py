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

import logging
import queue

import weewx.engine
import weewx.manager
import weewx.restx
from weeutil.config import search_up
from weeutil.weeutil import to_bool, to_sorted_string

log = logging.getLogger(__name__)

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
         - supersede pws_url with mandatory 'server_url' from [[WundergroundLike]] 
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
            log.error("WundergroundLike: Missing required configuration. "
                      "Please ensure [StdRESTful][[WundergroundLike]] is properly configured "
                      "with 'station', 'password', and 'server_url' in weewx.conf")
            return

        log.info("WundergroundLike: Configuration loaded: %s", _ambient_dict)

        # force rapidfire false
        _ambient_dict['rapidfire'] = False

        # supersede default pws_url used in WU with server_url from weewx.conf
        # server_url is already in _ambient_dict from get_site_dict
        log.debug("WundergroundLike server_url: %s", _ambient_dict.get('server_url'))

        _essentials_dict = search_up(config_dict['StdRESTful']['WundergroundLike'], 'Essentials', {})

        log.debug("WundergroundLike essentials: %s", _essentials_dict)

        # Get the manager dictionary:
        _manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding')

        # The default is to not do an archive post if a rapidfire post
        # has been specified, but this can be overridden
        do_rapidfire_post = to_bool(_ambient_dict.pop('rapidfire', False))
        do_archive_post = to_bool(_ambient_dict.pop('archive_post',
                                                    not do_rapidfire_post))
        if do_archive_post:
            # Don't use setdefault - server_url is already set from config
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
                     _ambient_dict.get('station', 'UNKNOWN'))

        if do_rapidfire_post:
            _ambient_dict.setdefault('server_url', WundergroundLike.rf_url)
            _ambient_dict.setdefault('log_success', False)
            _ambient_dict.setdefault('log_failure', False)
            _ambient_dict.setdefault('max_backlog', 0)
            _ambient_dict.setdefault('max_tries', 1)
            _ambient_dict.setdefault('rtfreq', 2.5)
            self.cached_values = weewx.restx.CachedValues()
            self.loop_queue = queue.Queue()
            self.loop_thread = weewx.restx.AmbientLoopThread(
                self.loop_queue,
                _manager_dict,
                protocol_name="WundergroundLike-RF",
                essentials=_essentials_dict,
                **_ambient_dict)
            self.loop_thread.start()
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            log.info("WundergroundLike-RF: Data for station %s will be posted",
                     _ambient_dict.get('station', 'UNKNOWN'))

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
