#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  main.py
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
import json
import os
import queue
import shutil
import sys
import tempfile
import traceback

from jesse import fetch
from jesse import pushbullet_listener
from jesse import runner

import pushbullet
import smoke_zephyr.utilities

__version__ = '1.0'

def _run_scan(arguments, scan_target, allow_file=False):
	tmp_path = arguments.tmp_path
	if tmp_path is None:
		tmp_path = os.path.join(tempfile.gettempdir(), tempfile.gettempprefix() + smoke_zephyr.utilities.random_string_alphanumeric(8))

	fetch.smart_fetch(scan_target, tmp_path, allow_file=allow_file)

	scanner = runner.SubprocessRunner(
		tmp_path,
		shutil.which('python')
	)

	print('[*] scanning: ' + tmp_path)
	scanner.run()
	scanner.wait()
	if not arguments.save_path:
		shutil.rmtree(tmp_path)
	return scanner

def main_pushbullet(arguments):
	device_name = 'Bandit'
	account = pushbullet.Pushbullet(arguments.api_key)

	device = next((device for device in account.devices if device.nickname == device_name), None)
	if device is None:
		device = account.new_device(device_name)

	if not os.path.isdir(arguments.report_directory):
		os.makedirs(arguments.report_directory)
		print('[*] created report directory: ' + arguments.report_directory)

	work_queue = queue.Queue()
	listener = pushbullet_listener.PushbulletDeviceListener(account, device=device, on_push=work_queue.put)
	listener.start()

	print('[*] started listener for pushbullet links shared with: ' + device_name)

	while True:
		try:
			work_item = work_queue.get()
		except KeyboardInterrupt:
			break
		if work_item.get('type') != 'link':
			continue
		scan_target = work_item.get('url')
		if scan_target is None:
			continue
		if not 'source_device_iden' in work_item:
			continue
		requesting_device = next((device for device in account.devices if device.device_iden == work_item['source_device_iden']), None)
		if requesting_device is None:
			continue
		print("[*] received request to scan: {0} from {1}".format(scan_target, (requesting_device.nickname or requesting_device.device_iden)))
		scan_uid = smoke_zephyr.utilities.random_string_alphanumeric(8)
		try:
			scanner = _run_scan(arguments, scan_target)
			report = scanner.get_report()
		except Exception:
			account.push_note(
				'Bandit Scan Error',
				"An error occurred while scanning: {0}".format(scan_target),
				device=requesting_device
			)
			traceback.print_exc()
			continue
		metrics_totals = report['metrics']['_totals']
		summary = "high:{0} medium:{1} low:{2}".format(
			metrics_totals['SEVERITY.HIGH'],
			metrics_totals['SEVERITY.MEDIUM'],
			metrics_totals['SEVERITY.LOW']
		)
		report_text = ''
		report_text += "Title: {0}\nUID: {1}\nSummary: {2}".format(work_item['title'], scan_uid, summary)
		account.push_note(
			'Bandit Report Summary',
			report_text,
			device=requesting_device
		)
		print('[*] sent summary report: ' + summary)

		report_directory = os.path.join(arguments.report_directory, scan_uid)
		os.mkdir(report_directory)
		with open(os.path.join(report_directory, 'report.json'), 'w') as file_h:
			json.dump(report, file_h, sort_keys=True, indent=2, separators=(',', ': '))
		with open(os.path.join(report_directory, 'stderr.txt'), 'wb') as file_h:
			file_h.write(scanner.stderr)
		with open(os.path.join(report_directory, 'stdout.txt'), 'wb') as file_h:
			file_h.write(scanner.stdout)
	listener.close()

def main_scan(arguments):
	scanner = _run_scan(arguments, arguments.target, allow_file=True)
	report = scanner.get_report()

def main():
	parser = argparse.ArgumentParser(description='Jesse James (CLI) - Bandit Automated Scanner', conflict_handler='resolve')
	parser.add_argument('-p', '--path', dest='tmp_path', help='the temporary store path')
	parser.add_argument('-s', '--save', dest='save_path', action='store_true', default=False, help='don\'t delete scanned directories')
	parser.add_argument('-v', '--version', action='version', version='%(prog)s Version: ' + __version__)
	sub_parsers = parser.add_subparsers()

	parser_scan = sub_parsers.add_parser('scan', help='scan a single target')
	parser_scan.set_defaults(handler=main_scan)
	parser_scan.add_argument('target', help='the target url to scan')

	parser_pushbullet = sub_parsers.add_parser('pushbullet', help='scan links shared via pushbullet')
	parser_pushbullet.set_defaults(handler=main_pushbullet)
	parser_pushbullet.add_argument('--report-dir', dest='report_directory', default=os.getcwd(), help='the location to write reports to')
	parser_pushbullet.add_argument('api_key', help='the api key to use to access pushbullet')
	arguments = parser.parse_args()

	arguments.handler(arguments)

if __name__ == '__main__':
	main()
