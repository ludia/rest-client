"""Thin REST/JSON client based on Requests."""

from .client import RestClient
from requests.exceptions import HTTPError, RequestException

__all__ = [
    'HTTPError',
    'RequestException',
    'RestClient',
]
