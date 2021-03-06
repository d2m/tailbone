# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import webapp2


class Middleware(object):
  def __init__(self, app):
    self.app = app

  def __call__(self, environ, start_response):
    req = webapp2.Request(environ)
    resp = req.get_response(self.app)

    def copy_header(k):
      v = req.headers.get(k)
      if v:
        resp.headers[k] = v

    for x in ["Country", "Region", "City", "CityLatLong"]:
      k = "X-AppEngine-" + x
      copy_header(k)

    resp.headers["REMOTE_ADDR"] = req.remote_addr

    return resp(environ, start_response)
