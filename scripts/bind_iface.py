import sys
import socket
import requests
import contextlib


@contextlib.contextmanager
def bind_iface(iface=''):

    _socket = socket.socket

    class Socket(_socket):
        def __init__(self, *args, **kwargs):
            super(Socket, self).__init__(*args, **kwargs)
            if iface:
                self.setsockopt(socket.SOL_SOCKET, 25, iface)
    try:
        socket.socket = Socket
        yield
    finally:
        socket.socket = _socket


def test(url, iface=''):
    with bind_iface(iface):
        try:
            print requests.get(url, timeout=2).text.strip()
        except Exception as exc:
            print repr(exc)
            return False
        return True


if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else ''
    iface = sys.argv[2] if len(sys.argv) > 2 else ''
    if not (url.startswith('http://') or url.startswith('https://')):
        url = 'http://' + url
    sys.exit(0 if test(url, iface) else 1)
