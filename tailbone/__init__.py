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

import cgi
import functools
import json
import logging
import os
import re
try:
  import traceback
except:
  pass
import webapp2

from google.appengine import api
from google.appengine.ext import ndb

PREFIX = "/api/"
DEBUG = os.environ.get("SERVER_SOFTWARE", "").startswith("Dev")
JSONP = os.environ.get("JSONP", "false") == "true"


# Custom Exceptions
class AppError(Exception):
  pass


class BreakError(Exception):
  pass


class LoginError(Exception):
  pass


# Extensions to the jsonifying of python results
def json_extras(obj):
  """Extended json processing of types."""
  if hasattr(obj, "get_result"):  # RPC
    return obj.get_result()
  if hasattr(obj, "strftime"):  # datetime
    return obj.strftime("%Y-%m-%dT%H:%M:%S.") + str(obj.microsecond / 1000) + "Z"
  if isinstance(obj, ndb.GeoPt):
    return {"lat": obj.lat, "lon": obj.lon}
  if isinstance(obj, ndb.Key):
    return obj.urlsafe()
  return None


# Decorator to return the result of a function as json. It supports jsonp by default.
def as_json(func):
  """Returns json when callback in url"""
  @functools.wraps(func)
  def wrapper(self, *args, **kwargs):
    self.response.headers["Content-Type"] = "application/json"
    if DEBUG:
      self.response.headers["Access-Control-Allow-Origin"] = "*"
      self.response.headers["Access-Control-Allow-Methods"] = "POST,GET,PUT,PATCH,HEAD,OPTIONS"
      self.response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    try:
      resp = func(self, *args, **kwargs)
      if resp is None:
        resp = {}
    except BreakError as e:
      return
    except LoginError as e:
      self.response.set_status(401)
      url = api.users.create_login_url(self.request.url)
      resp = {
        "error": e.__class__.__name__,
        "message": e.message,
        "url": url
      }
    except (AppError, api.datastore_errors.BadArgumentError,
            api.datastore_errors.BadRequestError) as e:
      self.response.set_status(400)
      resp = {"error": e.__class__.__name__, "message": e.message}
    if not isinstance(resp, str) and not isinstance(resp, unicode):
      resp = json.dumps(resp, default=json_extras)
    if JSONP:
      callback = self.request.get("callback")
      if callback:
        self.response.headers["Content-Type"] = "text/javascript"
        resp = "%s(%s);".format(callback, resp)
    self.response.out.write(resp)
  return wrapper


# BaseHandler for error handling
class BaseHandler(webapp2.RequestHandler):
  def handle_exception(self, exception, debug):
    # Log the error.
    logging.error(exception)
    if traceback:
      logging.error(traceback.format_exc())

    # If the exception is a HTTPException, use its error code.
    # Otherwise use a generic 500 error code.
    if isinstance(exception, webapp2.HTTPException):
      self.response.set_status(exception.code)
    else:
      self.response.set_status(500)

    msg = {"error": exception.__class__.__name__, "message": str(exception)}
    self.response.out.write(json.dumps(msg))

re_json = re.compile(r"^application/json", re.IGNORECASE)


# Parse the body of an upload based on the type if you are trying to post a cgi.FieldStorage object
# you should instead upload those blob separately via the special /api/files url.
def parse_body(self):
  if re_json.match(self.request.content_type):
    data = json.loads(self.request.body)
  else:
    data = {}
    for k, v in self.request.POST.items():
      if isinstance(v, cgi.FieldStorage):
        raise AppError("Files should be uploaded separately as their own form to /api/files/ and \
            then their ids should be uploaded and stored with the object.")
      if type(v) in [str, unicode]:
        try:
          v = json.loads(v)
        except ValueError:
          pass
      # TODO(doug): Bug when loading multiple json lists with same key
      # TODO(doug): Bug when loading a number that should be a string representation of said number
      if k in data:
        current = data[k]
        if isinstance(current, list):
          current.append(v)
        else:
          data[k] = [current, v]
      else:
        data[k] = v
  return data or {}
