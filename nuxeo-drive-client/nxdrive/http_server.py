'''
Created on Feb 19, 2013

@author: mconstantin
'''

import sys

import cherrypy
from cherrypy import tools

from nxdrive import DEBUG
from nxdrive.logging_config import get_logger

log = get_logger(__name__)
        
class Terminator(object):
    exposed = True
    def GET(self):
        sys.exit()
        
        
def http_server_loop(server, **kwargs):
    """Wrapper to log uncaught exception in the sync thread"""
    try:
        server.start(**kwargs)
    except Exception, e:
        log.error("Error in http server thread: %s", e, exc_info=True)

class HttpServer(object):
    exposed = True
    def __init__(self, port, app):
        try:
            self.port = port
            self.app = app
        except Exception, e:
            log.debug("failed to start HTTP server on port %d: %s", port, e, exc_info=True)
            
    @tools.json_out()
    def GET(self, state=None, folder=None, transition='false'):
        if DEBUG:
            return self.app(state, folder, transition)
        else:
            try:
                return self.app(state, folder, transition)
            except Exception, e:
                cherrypy.response.status = '400 Bad Request'
                return {'error': str(e)}
            
    def start(self):
        conf = {
            'global': {
                'server.socket_host': '0.0.0.0',
                'server.socket_port': self.port,
            },
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            }
        }
        self.stop = Terminator()
        cherrypy.quickstart(self, '/', conf)
        
    
        