from enum import Enum

import cmarkgfm
import unicodedata
import os
import re
import io
from cmarkgfm.cmark import Options
from flask import current_app as app

# isort:imports-firstparty
from CTFd.cache import cache
from CTFd.models import Configs, db

string_types = (str,)
text_type = str
binary_type = bytes
_windows_device_files = (
    "CON",
    "AUX",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "LPT1",
    "LPT2",
    "LPT3",
    "PRN",
    "NUL",
)


def fixed_secure_filename(filename: str) -> str:
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("utf8", "ignore").decode("utf8")   # 编码格式改变
    for sep in os.path.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, " ")
    _filename_utf8_add_strip_re = re.compile(r'[^A-Za-z0-9_\u2E80-\uFE4F.-]')
    filename = str(_filename_utf8_add_strip_re.sub('', '_'.join(filename.split()))).strip('._')             # 添加新规则
    if (
            os.name == "nt"
            and filename
            and filename.split(".")[0].upper() in _windows_device_files
    ):
        filename = f"_{filename}"
    return filename


def markdown(md):
    return cmarkgfm.markdown_to_html_with_extensions(
        md,
        extensions=["autolink", "table", "strikethrough"],
        options=Options.CMARK_OPT_UNSAFE,
    )


def get_app_config(key, default=None):
    value = app.config.get(key, default)
    return value


@cache.memoize()
def _get_config(key):
    config = db.session.execute(
        Configs.__table__.select().where(Configs.key == key)
    ).fetchone()
    if config and config.value:
        value = config.value
        if value and value.isdigit():
            return int(value)
        elif value and isinstance(value, string_types):
            if value.lower() == "true":
                return True
            elif value.lower() == "false":
                return False
            else:
                return value
    # Flask-Caching is unable to roundtrip a value of None.
    # Return an exception so that we can still cache and avoid the db hit
    return KeyError


def get_config(key, default=None):
    # Convert enums to raw string values to cache better
    if isinstance(key, Enum):
        key = str(key)

    value = _get_config(key)
    if value is KeyError:
        return default
    else:
        return value


def set_config(key, value):
    config = Configs.query.filter_by(key=key).first()
    if config:
        config.value = value
    else:
        config = Configs(key=key, value=value)
        db.session.add(config)
    db.session.commit()

    # Convert enums to raw string values to cache better
    if isinstance(key, Enum):
        key = str(key)

    cache.delete_memoized(_get_config, key)
    return config
