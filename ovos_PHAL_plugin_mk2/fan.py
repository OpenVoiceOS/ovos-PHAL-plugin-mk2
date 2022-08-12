# Copyright 2020 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import abc
import subprocess
import threading

from ovos_utils.log import LOG


class TemperatureMonitorThread(threading.Thread):
    def __init__(self, fan_obj=None):
        self.fan_obj = fan_obj or FanControl()
        self.exit_flag = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        LOG.debug("temperature monitor thread started")
        while not self.exit_flag.wait(60):
            LOG.debug(f"CPU temperature is {self.fan_obj.get_cpu_temp()}")

            # TODO make this ratiometric
            current_temperature = self.fan_obj.get_cpu_temp()
            if current_temperature < 50.0:
                # anything below 122F we are fine
                self.fan_obj.set_fan_speed(0)
                LOG.debug("Fan turned off")
                continue

            if 50.0 < current_temperature < 60.0:
                # 122 - 140F we run fan at 25%
                self.fan_obj.set_fan_speed(25)
                LOG.debug("Fan set to 25%")
                continue

            if 60.0 < current_temperature <= 70.0:
                # 140 - 160F we run fan at 50%
                self.fan_obj.set_fan_speed(50)
                LOG.debug("Fan set to 50%")
                continue

            if current_temperature > 70.0:
                # > 160F we run fan at 100%
                self.fan_obj.set_fan_speed(100)
                LOG.debug("Fan set to 100%")
                continue


class FanControl:
    # hardware speed range is appx 30-255
    # we convert from 0 to 100
    HDW_MIN = 0
    HDW_MAX = 255
    SFW_MIN = 0
    SFW_MAX = 100

    def __init__(self):
        self.fan_speed = 0
        self.set_fan_speed(self.fan_speed)

    def execute_cmd(self, cmd):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        out, err = process.communicate()

        try:
            out = out.decode('utf8')
        except:
            pass

        try:
            err = err.decode('utf8')
        except:
            pass

        return out, err

    def cToF(self, temp):
        return (temp * 1.8) + 32

    def speed_to_hdw_val(self, speed):
        out_steps = self.HDW_MAX - self.HDW_MIN
        in_steps = self.SFW_MAX - self.SFW_MIN
        ratio = out_steps / in_steps
        # force compliance
        if speed > self.SFW_MAX:
            speed = self.SFW_MAX
        if speed < self.SFW_MIN:
            speed = self.SFW_MIN

        return int((speed * ratio) + self.HDW_MIN)

    def hdw_val_to_speed(self, hdw_val):
        out_steps = self.SFW_MAX - self.SFW_MIN
        in_steps = self.HDW_MAX - self.HDW_MIN
        ratio = out_steps / in_steps
        # force compliance
        if hdw_val > self.HDW_MAX:
            hdw_val = self.HDW_MAX
        if hdw_val < self.HDW_MIN:
            hdw_val = self.HDW_MIN

        return int(round(((hdw_val - self.HDW_MIN) * ratio) + self.SFW_MIN, 0))

    def hdw_set_speed(self, hdw_speed):
        # force compliance
        if hdw_speed > self.HDW_MAX:
            hdw_speed = self.HDW_MAX
        if hdw_speed < self.HDW_MIN:
            hdw_speed = self.HDW_MIN

        hdw_speed = str(hdw_speed)
        cmd = ["i2cset", "-a", "-y", "1", "0x04", "101", hdw_speed, "i"]
        out, err = self.execute_cmd(cmd)

    def set_fan_speed(self, speed):
        self.fan_speed = self.speed_to_hdw_val(speed)
        self.hdw_set_speed(self.fan_speed)

    def get_fan_speed(self):
        return self.hdw_val_to_speed(self.fan_speed)

    def get_cpu_temp(self):
        cmd = ["cat", "/sys/class/thermal/thermal_zone0/temp"]
        out, err = self.execute_cmd(cmd)
        return float(out.strip()) / 1000


class MycroftFan:
    """ abstract base class for a Mycroft Fan
     all fan classes must provide at least
     these basic methods """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def set_fan_speed(self, new_speed):
        """takes in value between 0 - 100
           converts to internal format"""
        return

    @abc.abstractmethod
    def get_fan_speed(self):
        """returns value between 0-100"""

    @abc.abstractmethod
    def get_cpu_temp(self):
        """returns temp in celsius"""
        return
