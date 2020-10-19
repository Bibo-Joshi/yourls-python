# coding: utf-8
from yourls import YOURLSHTTPError, YOURLSAPIError, YOURLSKeywordExistsError


class YOURLSURLNotExistsError(YOURLSAPIError):
    """Raised when a requested short url does not exist.

    .. attribute:: keyword

       :obj:`str` for existing keyword.
    """
    def __init__(self, *args, **kwargs):
        self.keyword = kwargs.pop('keyword', None)
        self.url = kwargs.pop('url', None)
        if self.url:
            msg = 'URL {} does not exist.'.format(self.url)
        else:
            msg = 'Short URL {} does not exist.'.format(self.keyword)
        super(YOURLSURLNotExistsError, self).__init__(msg, *args, **kwargs)


class YOURLSDeleteMixin(object):
    def delete(self, short):
        data = dict(action='delete', shorturl=short)
        try:
            self._api_request(params=data)
        except YOURLSHTTPError as e:
            if str(e) == 'error: not found':
                raise YOURLSURLNotExistsError(keyword=short)
            else:
                raise e


class YOURLSEditUrlMixin(object):
    def geturl(self, url):
        data = dict(action='geturl', url=url)
        try:
            response = self._api_request(params=data)
            return response['keyword']
        except YOURLSHTTPError as e:
            if str(e) == 'error: not found':
                raise YOURLSURLNotExistsError(url=url)
            else:
                raise e

    def update(self, shorturl, url, title=None, use_current_title=False):
        if not title and use_current_title:
            title = 'keep'
        data = dict(action='update', shorturl=shorturl, url=url, title=title)
        try:
            self._api_request(params=data)
        except YOURLSHTTPError as e:
            if str(e) == 'error: not found':
                raise YOURLSURLNotExistsError(keyword=shorturl)
            else:
                raise e

    def change_keyword(self, newshorturl, oldshorturl=None,url=None, title=None,use_current_title=None):
        if not title and use_current_title:
            title = 'keep'
        data = dict(action='change_keyword', newshorturl=newshorturl, oldshorturl=oldshorturl, url=url, title=title)
        try:
            self._api_request(params=data)
        except YOURLSHTTPError as e:
            if str(e) == 'error: not found':
                raise YOURLSURLNotExistsError(keyword=newshorturl)
            if str(e) == 'error: already exists':
                raise YOURLSKeywordExistsError(keyword=newshorturl) from e
            raise e
