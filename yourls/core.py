# coding: utf-8
from __future__ import absolute_import, division, print_function

import hashlib
import time

import requests

from .data import (
    DBStats, _json_to_shortened_url, _validate_yourls_response)


class YOURLSClientBase(object):
    """
    Base class for YOURLS client that provides initializer and api request method.

    Note:
        :attr:`username` and :attr:`password` are mutually exclusive to :attr:`signature`.

    Args:
        apiurl (:obj:`str`): The URL of your YOURLS instance. You may skip the ``yourls-api.php``
            extension.
        username (:obj:`str`, optional): Your username.
        password (:obj:`str`, optional): Your password.
        signature (:obj:`str`, optional): Your signature.
        nonce_life (:obj:`bool` | :obj:`int`, optional): Whether to use timed limited signatures.
            Passing :obj:`True` will refresh the token after 12 hours. To use another value, pass
            the expiration time in seconds. Can only be used, if :attr:`signature` is passed.
    """
    def __init__(self, apiurl, username=None, password=None, signature=None, nonce_life=None):
        if (not bool(username and password) ^ bool(signature)
                or (nonce_life and not signature)):
            raise TypeError(
                'If server requires authentication, either pass username and '
                'password or signature. Otherwise, leave set to default (None). nonce_life may '
                'only be passed, if signature is passed.')

        self.apiurl = apiurl
        self.username = username
        self.password = password
        self.signature = signature
        self.nonce_life = nonce_life
        self._nonce_cache_time = None
        self._cached_signature = None

        if self.nonce_life is True:
            self.nonce_life = 43200
        if 'yourls-api.php' not in self.apiurl:
            self.url = self.apiurl.rstrip('/')
            self.apiurl = self.apiurl.rstrip('/') + '/yourls-api.php'
        else:
            self.url = self.apiurl[:-15]

    def timed_signature(self):
        """
        Current timestamp and MD5-encoded signature.

        Returns:
            Tuple(:obj:`int`, :obj:`str`)
        """
        timestamp = int(time.time())
        if not self._cached_signature or timestamp - self._nonce_cache_time > self.nonce_life:
            self._cached_signature = hashlib.md5(
                '{}{}'.format(timestamp, self.signature).encode('utf8')).hexdigest()
            self._nonce_cache_time = timestamp
        return self._nonce_cache_time, self._cached_signature

    @property
    def _data(self):
        data = {'format': 'json'}

        if self.username:
            data.update({'username': self.username, 'password': self.password})
        elif self.signature and not self.nonce_life:
            data.update({'signature': self.signature})
        elif self.signature and self.nonce_life:
            timestamp, signature = self.timed_signature()
            data.update({'signature': signature, 'timestamp': timestamp})

        return data

    def _api_request(self, params):
        params = params.copy()
        params.update(self._data)

        response = requests.get(self.apiurl, params=params)
        jsondata = _validate_yourls_response(response, params)
        return jsondata


class YOURLSAPIMixin(object):
    """Mixin to provide default YOURLS API methods."""
    def shorten(self, url, keyword=None, title=None):
        """Shorten URL with optional keyword and title.

        Parameters:
            url: URL to shorten.
            keyword: Optionally choose keyword for short URL, otherwise automatic.
            title: Optionally choose title, otherwise taken from web page.

        Returns:
            ShortenedURL: Shortened URL and associated data.

        Raises:
            ~yourls.exceptions.YOURLSKeywordExistsError: The passed keyword
                already exists.

                .. note::

                    This exception has a ``keyword`` attribute.

            ~yourls.exceptions.YOURLSURLExistsError: The URL has already been
                shortened.

                .. note::

                    This exception has a ``url`` attribute, which is an instance
                    of :py:class:`ShortenedURL` for the existing short URL.

            ~yourls.exceptions.YOURLSNoURLError: URL missing.

            ~yourls.exceptions.YOURLSNoLoopError: Cannot shorten a shortened URL.

            ~yourls.exceptions.YOURLSAPIError: Unhandled API error.

            ~yourls.exceptions.YOURLSHTTPError: HTTP error with response from
                YOURLS API.

            requests.exceptions.HTTPError: Generic HTTP error.
        """
        data = dict(action='shorturl', url=url, keyword=keyword, title=title)
        jsondata = self._api_request(params=data)

        url = _json_to_shortened_url(jsondata['url'], jsondata['shorturl'])

        return url

    def expand(self, short):
        """Expand short URL or keyword to long URL.

        Parameters:
            short: Short URL (``http://example.com/abc``) or keyword (abc).

        :return: Expanded/long URL, e.g.
                 ``https://www.youtube.com/watch?v=dQw4w9WgXcQ``

        Raises:
            ~yourls.exceptions.YOURLSHTTPError: HTTP error with response from
                YOURLS API.
            requests.exceptions.HTTPError: Generic HTTP error.
        """
        data = dict(action='expand', shorturl=short)
        jsondata = self._api_request(params=data)

        return jsondata['longurl']

    def url_stats(self, short):
        """Get stats for short URL or keyword.

        Parameters:
            short: Short URL (http://example.com/abc) or keyword (abc).

        Returns:
            ShortenedURL: Shortened URL and associated data.

        Raises:
            ~yourls.exceptions.YOURLSHTTPError: HTTP error with response from
                YOURLS API.
            requests.exceptions.HTTPError: Generic HTTP error.
        """
        data = dict(action='url-stats', shorturl=short)
        jsondata = self._api_request(params=data)

        return _json_to_shortened_url(jsondata['link'])

    def stats(self, filter, limit, start=None):
        """Get stats about links.

        Parameters:
            filter: 'top', 'bottom', 'rand', or 'last'.
            limit: Number of links to return from filter.
            start: Optional start number.

        Returns:
            Tuple containing list of ShortenedURLs and DBStats.

        Example:

            .. code-block:: python

                links, stats = yourls.stats(filter='top', limit=10)

        Raises:
            ValueError: Incorrect value for filter parameter.
            requests.exceptions.HTTPError: Generic HTTP Error
        """
        # Normalise random to rand, even though it's accepted by API.
        if filter == 'random':
            filter = 'rand'

        valid_filters = ('top', 'bottom', 'rand', 'last')
        if filter not in valid_filters:
            msg = 'filter must be one of {}'.format(', '.join(valid_filters))
            raise ValueError(msg)

        data = dict(action='stats', filter=filter, limit=limit, start=start)
        jsondata = self._api_request(params=data)

        stats = DBStats(total_clicks=int(jsondata['stats']['total_clicks']),
                        total_links=int(jsondata['stats']['total_links']))

        if 'links' in jsondata:
            links = [_json_to_shortened_url(jsondata['links'][key]) for key in jsondata['links']]
        else:
            links = []

        return links, stats

    def db_stats(self):
        """Get database statistics.

        Returns:
            DBStats: Total clicks and links statistics.

        Raises:
            requests.exceptions.HTTPError: Generic HTTP Error
        """
        data = dict(action='db-stats')
        jsondata = self._api_request(params=data)

        stats = DBStats(total_clicks=int(jsondata['db-stats']['total_clicks']),
                        total_links=int(jsondata['db-stats']['total_links']))

        return stats


class YOURLSClient(YOURLSAPIMixin, YOURLSClientBase):
    """YOURLS client."""
