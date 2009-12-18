#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2004-2009 Edgewall Software
# Copyright (C) 2004-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2005 Matthew Good <trac@matt-good.net>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.
#
# Author: Christopher Lenz <cmlenz@gmx.de>
#         Matthew Good <trac@matt-good.net>

import os
import sys
import pkg_resources
import urllib
from trac import __version__ as VERSION
from trac.web.wsgi import WSGIGateway, _ErrorsWrapper
from trac.web.auth import BasicAuthentication#, DigestAuthentication

class InputWrapper(object):

	def __init__(self, connection):
		self.connection = connection

	def close(self):
		pass

	#def read(self, size=-1):
	#	return self.connection.post_body[ :size ]

	#def readline(self, size=-1):
	#	return self.req.readline(size)

	#def readlines(self, hint=-1):
	#	return self.req.readlines(hint)

class ZimrTracGateway( WSGIGateway ):

	def __init__( self, connection, environ ):

		environ[ 'trac.web.frontend' ] = 'zimr'
		environ[ 'trac.web.version' ] = '0.1'

		for key in connection.request.headers.keys():
			environ[ "HTTP_" + key.upper() ] = connection.request.headers[ key ]

		environ[ 'SERVER_PORT' ] = 80
		environ[ 'SERVER_NAME' ] = "localhost"
		environ[ 'REQUEST_METHOD' ] = "get"
		environ[ 'REQUEST_URI' ] = connection.request.url
		environ[ 'PATH_INFO' ] = connection.request.url
		environ[ 'SCRIPT_NAME' ] = "" #root uri
		WSGIGateway.__init__( self, environ, InputWrapper( connection ),
							 _ErrorsWrapper( lambda x: req.log_error( x ) ) )
		self.connection = connection

	def _send_headers( self ):
		assert self.headers_set, 'Response not started'

		if not self.headers_sent:
			status, headers = self.headers_sent = self.headers_set
			self.connection.response.setStatus( int( status[ :3 ] ) )
			for name, value in headers:
				self.connection.response.headers[ name ] = value

	def _sendfile( self, fileobj ):
		self._send_headers()
		try:
			self.connection.sendFile( fileobj.name )
		except IOError, e:
			if 'client closed connection' not in str( e ):
				raise

	def _write( self, data ):
		self._send_headers()
		try:
			self.connection.send( data )
		except IOError, e:
			if 'client closed connection' not in str( e ):
				raise

class AuthenticationMiddleware(object):

	def __init__( self, application, auth ):
		self.application = application
		self.auth = auth

	def __call__( self, environ, start_response ):
		path_info = environ.get('PATH_INFO', '')
		path_parts = filter(None, path_info.split('/'))
		if len(path_parts) and path_parts[0] == 'login':
			remote_user = self.auth.do_auth(environ, start_response)
			if not remote_user:
				return []
			environ[ 'REMOTE_USER' ] = remote_user
			environ[ 'HTTP_COOKIE' ] = None

		return self.application(environ, start_response)

project_path = "."

def connection_handler( connection ):
	reload( sys.modules[ 'trac.web' ] )
	pkg_resources.require( 'Trac==%s' % VERSION )
	gateway = ZimrTracGateway( connection, { "trac.env_path": project_path } )
	from trac.web.main import dispatch_request
	gateway.run( AuthenticationMiddleware(
		dispatch_request,
		BasicAuthentication( os.path.abspath( os.path.join( project_path, ".htpasswd" ) ), connection.website.url )
	) )
