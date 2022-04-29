"""imagedata_format_pdf"""

import logging
import os
from os.path import join, exists
import subprocess

logging.getLogger(__name__).addHandler(logging.NullHandler())


if exists(join(__path__[0], "VERSION.txt")):
    _version_file = join(__path__[0], "VERSION.txt")
else:
    _version_file = "VERSION.txt"

try:
    from importlib.metadata import version, entry_points, PackageNotFoundError
    __version__ = version('imagedata_format_pdf')
except ModuleNotFoundError:
    from importlib_metadata import version, entry_points
    try:
        __version__ = version('imagedata_format_pdf')
    except (Exception, PackageNotFoundError):
        with open(_version_file, 'r') as fh:
            __version__ = fh.readline().strip()
except (Exception, PackageNotFoundError):
    # import imagedata_format_pdf as _
    # with open(join(_.__path__[0], "..", "VERSION.txt"), 'r') as fh:
    # with open(join(__path__[0], "..", "VERSION.txt"), 'r') as fh:
    with open(join(_version_file, 'r')) as fh:
        __version__ = fh.readline().strip()

__author__ = 'Erling Andersen, Haukeland University Hospital, Bergen, Norway'
__email__ = 'Erling.Andersen@Helse-Bergen.NO'

try:
    subprocess.call(
        ["pdfinfo", "-h"], stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w")
    )
    POPPLER_INSTALLED = True
except OSError as e:
    POPPLER_INSTALLED = e.errno != errno.ENOENT
