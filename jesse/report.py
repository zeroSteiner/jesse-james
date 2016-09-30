#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  report.py
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

import datetime
import json

import bandit

class Report(object):
	def __init__(self, data):
		self.data = data

	@classmethod
	def from_json_file(cls, filename):
		with open(filename, 'r') as file_h:
			data = json.load(file_h)
		return cls(data)

	@property
	def generated_at(self):
		return datetime.datetime.strptime(self.data['generated_at'], '%Y-%m-%dT%H:%M:%SZ')

	def results(self, min_confidence=None, min_severity=None):
		min_confidence = bandit.RANKING_VALUES[min_confidence or bandit.UNDEFINED]
		min_severity = bandit.RANKING_VALUES[min_severity or bandit.UNDEFINED]
		for result in self.data['results']:
			if bandit.RANKING_VALUES[result['issue_confidence']] < min_confidence:
				continue
			if bandit.RANKING_VALUES[result['issue_severity']] < min_severity:
				continue
			yield result
