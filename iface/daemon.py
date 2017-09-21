from twisted.internet import reactor
from twisted.python import log
import sys

from adselect.iface import server as iface_server
from adselect import db


log.startLogging(sys.stdout)

if __name__ == "__main__":
    db.configure_db()
    iface_server.configure_iface()
    reactor.run()
