#!/usr/bin/env python

import time

import RPi.GPIO as GPIO

from flask import Flask
from flask import request
app = Flask(__name__)

GPIO.setwarnings(False)


class RemoteSwitch(object):
        """
        Based on "elropi.py" for switching Elro devices using Python on Raspberry Pi
        by Heiko H. 2012
        """

        repeat = 10        # Number of transmissions
        pulselength = 300  # microseconds
        GPIOMode = GPIO.BCM

        def __init__(self, device, key=[1, 1, 1, 1, 1], pin=4):
                '''
                devices: A = 1, B = 2, C = 4, D = 8, E = 16
                key: according to dipswitches on your Elro receivers
                pin: according to Broadcom pin naming
                '''
                self.pin = pin
                self.key = key
                self.device = device
                GPIO.setmode(self.GPIOMode)
                GPIO.setup(self.pin, GPIO.OUT)

        def switchOn(self):
                self.toggle(GPIO.HIGH)

        def switchOff(self):
                self.toggle(GPIO.LOW)

        def toggle(self, switch, device=None, key=None):
                _key = key or self.key
                _device = device or self.device
                bit = [142, 142, 142, 142, 142, 142, 142, 142, 142, 142, 142, 136, 128, 0, 0, 0]

                for t in range(5):
                        if _key[t]:
                                bit[t] = 136
                x = 1
                for i in range(1, 6):
                        if _device & x > 0:
                                bit[4+i] = 136
                        x = x << 1

                if switch == GPIO.HIGH:
                        bit[10] = 136
                        bit[11] = 142

                bangs = []
                for y in range(16):
                        x = 128
                        for i in range(1, 9):
                                b = (bit[y] & x > 0) and GPIO.HIGH or GPIO.LOW
                                bangs.append(b)
                                x = x >> 1

                GPIO.output(self.pin, GPIO.LOW)
                for z in range(self.repeat):
                        for b in bangs:
                                GPIO.output(self.pin, b)
                                time.sleep(self.pulselength/1000000.)


device = RemoteSwitch(device=int(1),
                      key=[1, 1, 1, 1, 1],
                      pin=17)


@app.route("/switch/<dev>")
def switch(dev="1"):
        power = request.args.get('power', '')
        if power == 'on':
                device.toggle(GPIO.HIGH, device=int(dev))
        elif power == 'off':
                device.toggle(GPIO.LOW, device=int(dev))
        else:
                return '{"Error": "Invalid command"}'
        return '{"power": "%s"}' % power


if __name__ == '__main__':
        # app.register_error_handler(500, lambda e: 'bad request! ' + str(e))
        app.run(host='0.0.0.0')
