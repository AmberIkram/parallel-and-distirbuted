import hashlib, json, socket, struct, time

PROTOCOL_VERSION = 1


def sha256_file(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def send_json(sock, payload):
    data = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    sock.sendall(struct.pack('!I', len(data)) + data)


def recv_json(sock):
    header = _recv_exact(sock, 4)
    if not header:
        raise ConnectionError('Socket closed while reading message length')
    length = struct.unpack('!I', header)[0]
    if length > 10 * 1024 * 1024:
        raise ValueError('Message exceeds protocol limit')
    return json.loads(_recv_exact(sock, length).decode('utf-8'))


def send_file(sock, path, chunk_size=64 * 1024, progress=None):
    size = 0
    with open(path, 'rb') as f:
        while chunk := f.read(chunk_size):
            sock.sendall(chunk)
            size += len(chunk)
            if progress:
                progress(size)
    return size


def recv_file(sock, path, size, progress=None, timeout=30):
    received = 0
    old_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        with open(path, 'wb') as f:
            while received < size:
                chunk = sock.recv(min(64 * 1024, size - received))
                if not chunk:
                    raise ConnectionError('Socket disconnected during file transfer')
                f.write(chunk)
                received += len(chunk)
                if progress:
                    progress(received)
    finally:
        sock.settimeout(old_timeout)
    return received


def _recv_exact(sock, n):
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError('Socket closed unexpectedly')
        data.extend(chunk)
    return bytes(data)


def make_handshake(role):
    return {'type': 'handshake', 'protocol': PROTOCOL_VERSION, 'role': role, 'timestamp': time.time()}
