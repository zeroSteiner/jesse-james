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
import os
import re
import textwrap

import bandit
import jinja2
import pydoc
import pypandoc
import tabulate
import termcolor

jinja_env = jinja2.Environment(trim_blocks=True)
jinja_env.filters['strftime'] = lambda dt, fmt: dt.strftime(fmt)

MARKDOWN_TEMPLATE = jinja_env.from_string("""\
# Bandit Report
{% if extra.name %}
**{{ extra.name }}**

{{ extra.url }}

{% endif %}
Generated On {{ timestamp | strftime('%B %-d, %Y') }}
{% if python_version %}

Python Version {{ python_version }}
{% endif %}
\\newpage
\\tableofcontents
\\newpage

## Summary of Findings

{{ summary_table }}

*Shown as Confidence over Severity*

Total findings: {{ results | length }}

\\newpage

## All Findings

{% set level = None %}
{% for result in results %}
{% if level != result.issue_severity %}
### {{ result.issue_severity }} Findings
{% set level = result.issue_severity %}
{% endif %}
#### {{ result.test_name }} ({{ result.test_id }})

Severity: {{ result.issue_severity }}, Confidence: {{ result.issue_confidence }}

Description:

> {{ result.issue_text }}

Location: `{{ result.filename }}:{{ result.line_number }}`

Source Code:

```python
{% for line in result.code.split('\n') %}
{{ line }}
{% endfor %}
```
{% endfor %}
""")

class Report(object):
	def __init__(self, data):
		self.data = data

	@staticmethod
	def _colored_ranking(ranking):
		colors = {
			bandit.HIGH: 'red',
			bandit.MEDIUM: 'yellow',
			bandit.LOW: 'white',
			bandit.UNDEFINED: 'cyan',
		}
		return termcolor.colored(ranking, colors[ranking], attrs=('bold',))

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

	@property
	def sorted_results(self):
		results = self.data['results']
		results = sorted(results, key=lambda r: bandit.RANKING_VALUES[r['issue_confidence']])
		results = sorted(results, key=lambda r: bandit.RANKING_VALUES[r['issue_severity']])
		results.reverse()
		return results

	def to_json(self):
		return json.dumps(self.data, sort_keys=True, indent=2, separators=(',', ': '))

	def to_json_file(self, filename):
		with open(filename, 'w') as file_h:
			file_h.write(self.to_json())

	def to_markdown(self):
		results = self.sorted_results
		tally = lambda c, s: sum(1 for res in results if res['issue_confidence'] == c and res['issue_severity'] == s)
		summary_table = [[s] + [tally(c, s) for c in reversed(bandit.RANKING)] for s in reversed(bandit.RANKING)]
		summary_table = tabulate.tabulate(
			summary_table,
			headers=[''] + list(reversed(bandit.RANKING)),
			tablefmt='markdown'
		)
		text = MARKDOWN_TEMPLATE.render(
			extra=self.data.get('_jj'),
			results=results,
			python_version=self.data.get('python_version'),
			summary_table=summary_table,
			timestamp=self.generated_at
		)
		return text

	def to_pdf_file(self, filename):
		pypandoc.convert_text(self.to_markdown(), 'pdf', format='markdown', outputfile=filename)

	def to_text(self, maxwidth=80, use_color=True):
		results = self.sorted_results
		text = collections.deque()
		text.append(termcolor.colored('Report:', attrs=('bold', 'underline')))
		if '_jj' in self.data:
			text.append('  - Title:          ' + self.data['_jj']['name'])
			text.append('  - URL:            ' + self.data['_jj']['url'])
		text.append("  - Generated At:   {0:%b %d, %Y %H:%M}".format(self.generated_at))
		text.append("  - Python Version: {0}".format(self.data.get('python_version', 'UNKNOWN')))
		text.append("  - Total Findings: {0:,}".format(len(results)))
		text.append('')

		text.append(termcolor.colored('Summary:', attrs=('bold', 'underline')))
		tally = lambda c, s: sum(1 for res in results if res['issue_confidence'] == c and res['issue_severity'] == s)
		summary_table = [[s] + [tally(c, s) for c in reversed(bandit.RANKING)] for s in reversed(bandit.RANKING)]
		summary_table = tabulate.tabulate(
			summary_table,
			headers=[''] + list(reversed(bandit.RANKING)),
			tablefmt='grid'
		)
		text.extend(summary_table.split('\n'))
		text.append('| (Shown as Confidence over Severity)')
		text.append('+------------------------------------')
		text.append('')

		for result_id, result in enumerate(results, 1):
			header = ''
			header += "{0:<27}".format(termcolor.colored("Result #{0:,}".format(result_id), attrs=('bold', 'underline')))
			header += " [{0}: {1}]".format(result['test_id'], termcolor.colored(result['test_name'], attrs=('bold',)))
			text.append(header)
			text.append("  Severity: {0:<22} Confidence: {1}".format(
				self._colored_ranking(result['issue_severity']),
				self._colored_ranking(result['issue_confidence'])
			))
			text.append('  Description:')
			text.extend(['    ' + line for line in textwrap.wrap(result['issue_text'], width=maxwidth - 4)])
			text.append("  Source: {0}:{1}".format(result['filename'], result['line_number']))
			for line in result['code'].split('\n')[:-1]:
				if ' ' in line:
					text.append("    {0:<5}: {1}".format(*line.split(' ', 1)))
				else:
					text.append('    ' + line)
			text.append('')
		# text deque is fully created
		text = '\n'.join(text)
		if not use_color:
			ansi_escape = re.compile(r'\x1b[^m]*m')
			text = ansi_escape.sub('', text)
		return text

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Jesse James (CLI) - Bandit Report Manager', conflict_handler='resolve')
	parser.add_argument('-o', '--output', dest='output', type=argparse.FileType('w'), help='a file to write the report to')
	parser.add_argument('report_file', help='the report file to load')
	arguments = parser.parse_args()

	report = Report.from_json_file(arguments.report_file)
	report_text = report.to_text(use_color=(arguments.output is None or arguments.output.isatty()))

	if arguments.output:
		arguments.output.write(report_text)
	else:
		pydoc.pipepager(report_text, cmd='less -R')
