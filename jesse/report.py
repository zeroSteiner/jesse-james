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

import argparse
import collections
import datetime
import json
import textwrap

import bandit
import pydoc
import tabulate
import termcolor

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

	def to_text(self, maxwidth=80):
		results = sorted(self.data['results'], key=lambda r: bandit.RANKING_VALUES[r['issue_severity']])
		results.reverse()
		text = collections.deque()
		text.append('Report:')
		text.append("  - Generated At:   {0:%b %d, %Y %H:%M}".format(self.generated_at))
		text.append("  - Python Version: {0}".format(self.data.get('python_version', 'UNKNOWN')))
		text.append("  - Total Findings: {0:,}".format(len(results)))
		text.append('')

		text.append('Summary:')
		tally = lambda c, s: sum(1 for res in results if res['issue_confidence'] == c and res['issue_severity'] == s)
		summary_table = [[s] + [tally(c, s) for c in reversed(bandit.RANKING)] for s in reversed(bandit.RANKING)]
		summary_table = tabulate.tabulate(
			summary_table,
			headers=[''] + list(reversed(bandit.RANKING)),
			tablefmt='grid'
		)
		text.extend(summary_table.split('\n'))
		text.append('(Shown as Confidence over Severity)')
		text.append('')

		for result_id, result in enumerate(results, 1):
			text.append("Result #{0:<7,} {1} - {2}".format(result_id, result['test_id'], result['test_name']))
			text.append("  Severity: {0:<8} Confidence: {1}".format(result['issue_severity'], result['issue_confidence']))
			text.append('  Description:')
			text.extend(['    ' + line for line in textwrap.wrap(result['issue_text'], width=maxwidth - 4)])
			text.append("  Source: {0}:{1}".format(result['filename'], result['line_number']))
			for line in result['code'].split('\n')[:-1]:
				if ' ' in line:
					text.append("    {0:<5}: {1}".format(*line.split(' ', 1)))
				else:
					text.append('    ' + line)
			text.append('')
		return '\n'.join(text)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Jesse James (CLI) - Bandit Report Manager', conflict_handler='resolve')
	parser.add_argument('-o', '--output', dest='output', type=argparse.FileType('w'), help='a file to write the report to')
	parser.add_argument('report_file', help='the report file to load')
	arguments = parser.parse_args()

	report = Report.from_json_file(arguments.report_file)
	report_text = report.to_text()

	if arguments.output:
		arguments.output.write(report_text)
	else:
		pydoc.pager(report_text)
