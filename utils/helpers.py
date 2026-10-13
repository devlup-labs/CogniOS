

def rate_mb_s(current_bytes, last_bytes, elapsed_sec):

    if last_bytes is None or elapsed_sec <= 0:
        return None
    # how many bytes have been sent/received since the last check, and convert to MB/s by dividing by 1 MB
    delta_bytes = current_bytes - last_bytes
    return (delta_bytes / elapsed_sec) / (1024 * 1024)