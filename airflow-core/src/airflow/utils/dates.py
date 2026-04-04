#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import calendar

# Floating-point factors used when converting between datetime components and Unix timestamps.
_MICROSECONDS_PER_SECOND = 1e6
_NANOSECONDS_PER_SECOND = 1e9

cron_presets: dict[str, str] = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@quarterly": "0 0 1 */3 *",
    "@yearly": "0 0 1 1 *",
}


def datetime_to_nano(datetime) -> int | None:
    """Convert datetime to nanoseconds."""
    if datetime:
        if datetime.tzinfo is None:
            # There is no timezone info, handle it the same as UTC.
            timestamp = calendar.timegm(datetime.timetuple()) + datetime.microsecond / _MICROSECONDS_PER_SECOND
        else:
            # The datetime is timezone-aware. Use timestamp directly.
            timestamp = datetime.timestamp()
        return int(timestamp * _NANOSECONDS_PER_SECOND)
    return None
