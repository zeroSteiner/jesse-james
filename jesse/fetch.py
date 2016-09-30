#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  fetch.py
#
#  Copyright 2016 Spencer McIntyre <zeroSteiner@gmail.com>
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following disclaimer
#    in the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the  nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import base64
import collections
import ftplib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

import git
import smoke_zephyr.utilities

MAKEDIR_MODE = 0o770
Creds = collections.namedtuple('Creds', ('username', 'password'))

def _fetch_remote(source, destination, parsed_url, creds, tmp_file, tmp_path):
	if parsed_url['scheme'] in ('ftp', 'ftps'):
		if parsed_url['scheme'] == 'ftp':
			connection = ftplib.FTP()
			connection.connect(*smoke_zephyr.utilities.parse_server(parsed_url['netloc'], 21))
		else:
			connection = ftplib.FTP_TLS()
			connection.connect(*smoke_zephyr.utilities.parse_server(parsed_url['netloc'], 990))
		connection.login(creds.username or '', creds.password or '')
		connection.retrbinary('RETR ' + parsed_url['path'], tmp_file.write)
		connection.quit()
	elif parsed_url['scheme'] in ('git', 'git+ssh', 'git+http', 'git+https'):
		parsed_url['scheme'] = parsed_url['scheme'].split('+', 1)[-1]
		branch = parsed_url['fragment']
		if branch:
			parsed_url['fragment'] = ''
		else:
			branch = 'master'
		os.mkdir(destination, mode=MAKEDIR_MODE)
		repo = git.Repo.init(destination)
		origin = repo.create_remote('origin', urllib.parse.urlunparse(parsed_url.values()))
		origin.fetch()
		origin.pull('master')
		if branch == 'master':
			return
		branch_ref = next((ref for ref in repo.refs if isinstance(ref, git.RemoteReference) and ref.remote_head == branch), None)
		if branch_ref is None:
			raise ValueError('failed to find reference to remote branch name: ' + branch)
		branch_ref.checkout(b=branch)
	elif parsed_url['scheme'] in ('http', 'https'):
		request = urllib.request.Request(urllib.parse.urlunparse(parsed_url.values()))
		if creds.username is not None:
			request.add_header(
				'Authorization',
				'Basic ' + base64.b64encode("{0}:{1}".format(creds.username, creds.password).encode('utf-8')).decode('utf-8')
			)
		url_h = urllib.request.urlopen(request)
		shutil.copyfileobj(url_h, tmp_file)
		url_h.close()

def fetch(source, destination, allow_file=False):
	"""
	Fetch a group of files either from a file archive or version control
	repository.

	Supported URL schemes:
	  - file
	  - ftp
	  - ftps
	  - git
	  - git+http
	  - git+https
	  - git+ssh
	  - http
	  - https

	:param str source: The source URL to retrieve.
	:param str destination: The directory into which the files should be placed.
	:param bool allow_file: Whether or not to permit the file:// URL for processing local resources.
	:return: The destination directory that was used.
	:rtype: str
	"""
	source = source.strip()
	if os.path.exists(destination):
		raise ValueError('destination must not be an existing directory')

	parsed_url = urllib.parse.urlparse(source, scheme='file')
	if parsed_url.username is not None:
		# if the username is not none, then the password will be a string
		creds = Creds(parsed_url.username, parsed_url.password or '')
	else:
		creds = Creds(None, None)

	parsed_url = collections.OrderedDict(zip(('scheme', 'netloc', 'path', 'params', 'query', 'fragment'), parsed_url))
	parsed_url['netloc'] = parsed_url['netloc'].split('@', 1)[-1]
	parsed_url['scheme'] = parsed_url['scheme'].lower()


	if parsed_url['scheme'] == 'file':
		if not allow_file:
			raise RuntimeError('file: URLs are not allowed to be processed')
		tmp_path = parsed_url['path']
		if os.path.isdir(tmp_path):
			shutil.copytree(tmp_path, destination, symlinks=True)
		elif os.path.isfile(tmp_path):
			shutil.unpack_archive(tmp_path, destination)
	else:
		tmp_fd, tmp_path = tempfile.mkstemp(suffix='_' + os.path.basename(parsed_url['path']))
		os.close(tmp_fd)
		tmp_file = open(tmp_path, 'wb')
		try:
			_fetch_remote(source, destination, parsed_url, creds, tmp_file, tmp_path)
			if os.stat(tmp_path).st_size:
				shutil.unpack_archive(tmp_path, destination)
		finally:
			tmp_file.close()
			os.remove(tmp_path)
	return

def smart_fetch(source, destination, allow_file=False):
	source = source.strip()
	parsed_url = urllib.parse.urlparse(source, scheme='file')
	parsed_url = collections.OrderedDict(zip(('scheme', 'netloc', 'path', 'params', 'query', 'fragment'), parsed_url))
	parsed_url['scheme'] = parsed_url['scheme'].lower()
	if parsed_url['scheme'] in ('http', 'https'):
		# convert bitbucket.org project pages to git+https repos
		match = re.match(r'^/(?P<slug>[\w-]+/[\w-]+)(?:/branch/(?P<branch>\w+))?/?$', parsed_url['path'])
		if parsed_url['netloc'].lower() == 'bitbucket.org' and match is not None:
			parsed_url['scheme'] = 'git+https'
			parsed_url['path'] = match.group('slug') + '.git'
			parsed_url['fragment'] = match.group('branch')
		# convert github.com project pages to git+https repos
		match = re.match(r'^/(?P<slug>[\w-]+/[\w-]+)$', parsed_url['path'])
		if parsed_url['netloc'].lower() == 'gist.github.com' and match is not None:
			parsed_url['scheme'] = 'git+https'
			parsed_url['path'] = match.group('slug') + '.git'
		# convert github.com project pages to git+https repos
		match = re.match(r'^/(?P<slug>[\w-]+/[\w-]+)(?:/tree/(?P<branch>\w+))?/?$', parsed_url['path'])
		if parsed_url['netloc'].lower() == 'github.com' and match is not None:
			parsed_url['scheme'] = 'git+https'
			parsed_url['path'] = match.group('slug') + '.git'
			parsed_url['fragment'] = match.group('branch')

	source = urllib.parse.urlunparse(parsed_url.values())
	return fetch(source, destination, allow_file=allow_file)

def main():
	if len(sys.argv) < 3:
		print("usage: {0} [source] [destination]".format(sys.argv[0]))
		return 0
	destination = sys.argv[2]
	smart_fetch(sys.argv[1], destination)
	print('[*] saved to: ' + destination)
	return 0

if __name__ == '__main__':
	sys.exit(main())
