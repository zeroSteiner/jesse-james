#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  pushbullet_listener.py
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

import sys

import pushbullet

class PushbulletDeviceListener(pushbullet.Listener):
	def __init__(self, account, device, on_push=None, update_device=True):
		self.device = device
		if update_device:
			account.edit_device(
				device,
				model='.'.join(map(str, sys.version_info[:3])),
				manufacturer='Python'
			)
		self.last_push = account.get_pushes(limit=1)[0]
		super(PushbulletDeviceListener, self).__init__(account)
		self.on_push = self._on_push
		if on_push is not None:
			self.on_device_push = on_push

	def _on_push(self, data):
		if not (data.get('type') == 'tickle' and data.get('subtype') == 'push'):
			return
		for push in self._account.get_pushes(modified_after=self.last_push['modified']):
			if push.get('target_device_iden') != self.device.device_iden:
				continue
			self.on_device_push(push)
			self.last_push = push

	def on_device_push(self, push_message):
		pass
