#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  runner.py
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

import json
import os
import subprocess
import sys

import jesse.report

import smoke_zephyr.utilities

class SubprocessRunner(object):
	def __init__(self, target_path, python_bin_path=None):
		self.target_path = target_path
		self.proc_h = None
		self.python_bin_path = python_bin_path or sys.executable
		self.stdout = None
		self.stderr = None
		self.encoding = 'utf-8'
		self.timeout = smoke_zephyr.utilities.parse_timespan('30m')

	def run(self):
		self.proc_h = subprocess.Popen(
			[
				self.python_bin_path,
				'-m',
				'bandit.cli.main',
				'--format',
				'json',
				'--number',
				'11',
				'--recursive',
				self.target_path
			],
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE
		)

	def get_report(self):
		data = json.loads(self.stdout.decode(self.encoding))
		return jesse.report.Report(data)

	def wait(self):
		self.stdout, self.stderr = self.proc_h.communicate(timeout=self.timeout)

class PyenvSubprocessRunner(SubprocessRunner):
	def __init__(self, target_path, pyenv_path, pyenv_version):
		python_bin_path = os.path.abspath(os.path.join(pyenv_path, 'versions', pyenv_version, 'bin', 'python'))
		super(PyenvSubprocessRunner, self).__init__(target_path, python_bin_path)
		self.pyenv_path = pyenv_path
		self.pyenv_version = pyenv_version
