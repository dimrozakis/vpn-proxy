import math
import logging
import resource
import functools


log = logging.getLogger(__name__)


def bytes_units(number):
    """Translate a integer number of bytes to a float number of KiB, MiB etc"""
    units = ('B', 'KiB', 'MiB', 'GiB')
    index = int(math.log(number, 2) / 10)
    ret = ('%.1f' if index else '%d') % (float(number) / 2 ** (10 * index))
    return '%s %s' % (ret, units[index])


def get_mem_usage():
    """Return a human readable string of current memory consumption"""
    kbytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return 'Memory usage: %s.' % bytes_units(kbytes * 1024)


def memory_decorator(func):
    """Wrap a function to print memory usage after completion"""

    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            log.info(get_mem_usage())
