"""
pico_serial.py
Simple serial client for Raspberry Pi Pico2 according to Interface.md.

Requirements:
  pip install pyserial

Usage in Flask app:
  from pico_serial import PicoSerial, parse_pi_message

Default baud: 115200
Behavior:
  - Messages terminated by LF ("\n"). UTF-8. Max 64 bytes validated.
  - On send, waits up to 1s for [PI]:ACK:<CMD> then retries once.
"""
from argparse import ArgumentParser
import serial
import time
import threading

MAX_LEN = 64
DEFAULT_BAUD = 115200
ACK_TIMEOUT = 1.0
RETRY_COUNT = 1

class PicoSerial:
    def __init__(self, port, baud=DEFAULT_BAUD):
        # non-blocking read with small timeout
        self.ser = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        self.lock = threading.Lock()

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def send_raw(self, line: str):
        if not line.endswith('\n'):
            line = line + '\n'
        data = line.encode('utf-8')
        if len(data) > MAX_LEN:
            raise ValueError('message too long')
        with self.lock:
            self.ser.write(data)

    def read_line(self):
        try:
            raw = self.ser.readline()
            if not raw:
                return None
            # preserve exact content except remove trailing LF
            s = raw.decode('utf-8', errors='replace')
            if s.endswith('\n'):
                s = s[:-1]
            return s
        except Exception:
            return None

    def send_and_wait_ack(self, out_line: str, cmd_tag: str) -> bool:
        for attempt in range(RETRY_COUNT + 1):
            self.send_raw(out_line)
            deadline = time.time() + ACK_TIMEOUT
            while time.time() < deadline:
                ln = self.read_line()
                if not ln:
                    continue
                # Example ACK: [PI]:ACK:LED
                if ln.startswith('[PI]:ACK:'):
                    parts = ln.split(':')
                    if len(parts) >= 3 and parts[2] == cmd_tag:
                        return True
                # If error received, stop early
                if ln.startswith('[PI]:ERR:'):
                    return False
            # no ACK, will retry
        return False

# Simple parser for PI messages per Interface.md

def parse_pi_message(line: str):
    if not line.startswith('[PI]:'):
        return {'type': 'UNKNOWN', 'raw': line}
    try:
        parts = line.split(':')
        if len(parts) < 3:
            return {'type': 'MALFORMED', 'raw': line}
        tag = parts[1]
        if tag == 'LED':
            payload = parts[2]
            return {'type': 'LED', 'payload': payload}
        if tag == 'BTN':
            payload = parts[2]
            return {'type': 'BTN', 'payload': payload}
        if tag == 'NTF':
            if len(parts) >= 4:
                evt = parts[2]
                state = parts[3]
                return {'type': 'NTF', 'event': evt, 'state': state}
        if tag == 'ACK':
            return {'type': 'ACK', 'cmd': parts[2] if len(parts) >=3 else None}
        if tag == 'ERR':
            code = parts[2] if len(parts) >=3 else None
            msg = parts[3] if len(parts) >=4 else None
            return {'type': 'ERR', 'code': code, 'msg': msg}
        return {'type': tag, 'raw': line}
    except Exception as e:
        return {'type': 'PARSE_ERROR', 'error': str(e), 'raw': line}

# Convenience builders

def build_led_set_cmd(id_str, ctrl):
    return f'[PC]:LED:SET:{id_str}:{ctrl}\n'

def build_led_bulk_cmd(eightchars):
    return f'[PC]:LED:{eightchars}\n'

def build_sta_cmd(which):
    return f'[PC]:STA:{which}\n'

if __name__ == '__main__':
    p = ArgumentParser()
    p.add_argument('--port', required=True)
    p.add_argument('--baud', type=int, default=DEFAULT_BAUD)
    args = p.parse_args()
    client = PicoSerial(args.port, baud=args.baud)
    try:
        print('Listening... Ctrl-C to stop')
        while True:
            ln = client.read_line()
            if ln:
                print(ln)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()
