'''
Created on Feb 19, 2013

@author: mconstantin
'''

#from wsgiref.simple_server import make_server
import cherrypy
from nxdrive.logging_config import get_logger

log = get_logger(__name__)


#def http_server_loop(server, **kwargs):
#    """Wrapper to log uncaught exception in the sync thread"""
#    try:
#        server.loop(**kwargs)
#    except Exception, e:
#        log.error("Error in http server thread: %s", e, exc_info=True)
#
#class HttpServer(object):
#    def __init__(self, port, app):
#        try:
#            self.httpd = make_server('', port, app)
#        except Exception, e:
#            log.debug("failed to start HTTP server on port %d: %s", port, e, exc_info=True)
#            
#    def loop(self):
#        self.httpd.serve_forever()
#        
#    def stop(self):
#        self.httpd.shutdown()
#        self.httpd = None
        
def http_server_loop(server, **kwargs):
    """Wrapper to log uncaught exception in the sync thread"""
    try:
        server.loop(**kwargs)
    except Exception, e:
        log.error("Error in http server thread: %s", e, exc_info=True)

class HttpServer(object):
    def __init__(self, port, app):
        try:
            self.app = app
            cherrypy.server.socket_host = '0.0.0.0'
            cherrypy.server.socket_port = port
        except Exception, e:
            log.debug("failed to start HTTP server on port %d: %s", port, e, exc_info=True)
            
    def index(self):
        self.app()
        
    index.exposed = True
    
    def loop(self):
        cherrypy.quickstart(HttpServer())
        
    def stop(self):
        pass
        
        