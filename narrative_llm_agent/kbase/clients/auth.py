import time
from narrative_llm_agent.config import get_config
import requests
from cacheout.lru import LRUCache


def _get(url: str, headers: dict[str, str]) -> dict:
    response = requests.get(url, headers=headers)
    _check_error(response)
    return response.json()


def _check_error(response: requests.Response):
    if response.status_code != 200:
        try:
            resp_data = response.json()
        except Exception:
            err = "Non-JSON response from KBase auth server, status code: " + str(response.status_code)
            raise IOError(err)
        # assume that if we get json then at least this is the auth server and we can
        # rely on the error structure.
        err = resp_data["error"].get("appcode")
        if err == 10020:  # Invalid token
            raise InvalidTokenError("KBase auth server reported token is invalid.")
        if err == 30010:  # Illegal username
            # The auth server does some goofy stuff when propagating errors, should be cleaned up
            # at some point
            raise InvalidUserError(resp_data["error"]["message"].split(":", 3)[-1])
        # don't really see any other error codes we need to worry about - maybe disabled?
        # worry about it later.
        raise IOError("Error from KBase auth server: " + resp_data["error"]["message"])


class KBaseAuth:
    """
    A very very simple KBase auth client.
    Only provides a way to check a token's validity by getting a user name.
    Not async. That's a whole other issue here meshing with AI packages.
    """
    def __init__(self, endpoint: str = None, cache_max_size: int = 10000, cache_expiration: int = 300) -> None:
        if endpoint is None:
            endpoint = get_config().auth_endpoint
        self._endpoint = endpoint
        self._token_url = self._endpoint + "/api/V2/token"
        self._user_url = self._endpoint + "/api/V2/users?list="
        self._cache_timer = time.time  # TODO TEST figure out how to replace the timer to test
        # cache is intended to map tokens -> usernames
        self._cache = LRUCache(
            timer=self._cache_timer, maxsize=cache_max_size, ttl=cache_expiration
        )

    def get_user(self, token: str) -> str:
        """
        Returns the user id associated with the given auth token.
        Raises errors otherwise.
        """
        if token in self._cache:
            return self._cache.get(token)
        result = _get(self._token_url, {"Authorization": token})
        self._cache.set(token, result["user"])
        return result["user"]

    def get_user_display_name(self, token: str) -> dict[str, str]:
        """
        Returns the user name and display name associated with the token as a small dictionary.
        {
            user_name: username (wjriehl),
            display_name: full username (William Riehl)
        }
        """
        if token in self._cache:
            username = self._cache.get(token)
        else:
            username = self.get_user(token)

        result = _get(self._user_url + username, {"Authorization": token})
        return {
            "user_name": username,
            "display_name": result.get(username, "Unknown")
        }


class AuthenticationError(Exception):
    """An error thrown from the authentication service."""


class InvalidTokenError(AuthenticationError):
    """An error thrown when a token is invalid."""


class InvalidUserError(AuthenticationError):
    """An error thrown when a username is invalid."""
