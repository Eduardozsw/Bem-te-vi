import logging
import os

import yaml

logger = logging.getLogger(__name__)

PROFILE_PATH = "profile.yaml"


def _parse(text: str, source: str) -> dict:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        logger.warning("Invalid profile YAML from %s: %s", source, e)
        return {}
    if not isinstance(data, dict):
        if data is not None:
            logger.warning("Profile from %s is not a mapping; ignoring", source)
        return {}
    return data


def load_profile() -> dict:
    env = os.getenv("USER_PROFILE")
    if env:
        return _parse(env, "USER_PROFILE env var")
    try:
        with open(PROFILE_PATH, encoding="utf-8") as f:
            return _parse(f.read(), PROFILE_PATH)
    except FileNotFoundError:
        return {}
