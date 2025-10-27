r"""
Relay
./_build/moxygen/relay/moqrelayserver -port 4433 -cert ./certs/certificate.pem -key ./certs/certificate.key -endpoint "/moq" --logging DBG1

Video source
mkfifo ~/Movies/fifo.flv
ffmpeg -y -f lavfi -re -i smptebars=duration=300:size=320x200:rate=30 -f lavfi -re -i sine=frequency=1000:duration=300:sample_rate=48000 -pix_fmt yuv420p -c:v libx264 -b:v 180k -g 60 -keyint_min 60 -profile:v baseline -preset veryfast -c:a aac -b:a 96k -vf "drawtext=fontfile=/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf: text=\'Local time %{localtime\: %Y\/%m\/%d %H.%M.%S} (%{n})\': x=10: y=10: fontsize=16: fontcolor=white: box=1: boxcolor=0x00000099" -f flv ~/Movies/fifo.flv

Streamer command
./_build/moxygen/samples/flv_streamer_client/moqflvstreamerclient -input_flv_file ~/Movies/fifo.flv -connect_url "https://192.168.221.128:4433/moq" --logging DBG1

Receiver command
./_build/moxygen/samples/flv_receiver_client/moqflvreceiverclient -connect_url "https://192.168.221.128:4433/moq" --flv_outpath ~/Movies/moq-out-test.flv -stats_log_file "./test.log" --logging DBG1
"""

import subprocess as sp
import time
import os
import stat

PIPE_PATH = "~/Movies/fifo.flv"
VM_IP = "192.168.221.128"
RELAY_URL = "https://192.168.221.128:4433/moq"


def start_relay_server():
    # SSH into the relay server and start the relay process
    cmd = [
        "ssh", "user@" + VM_IP,
        "./_build/moxygen/relay/moqrelayserver",
        "-port", "4433",
        "-cert", "./certs/certificate.pem",
        "-key", "./certs/certificate.key",
        "-endpoint", "/moq",
        "--logging", "DBG1"
    ]
    return sp.Popen(cmd)


def start_video_source():
    # Ensure the named pipe exists (expand ~) and is actually a FIFO.
    fifo_path = os.path.expanduser(PIPE_PATH)
    fifo_dir = os.path.dirname(fifo_path)
    if fifo_dir and not os.path.exists(fifo_dir):
        os.makedirs(fifo_dir, exist_ok=True)

    if os.path.exists(fifo_path):
        st = os.stat(fifo_path)
        if not stat.S_ISFIFO(st.st_mode):
            # If a regular file exists at the path, remove and recreate as FIFO
            os.remove(fifo_path)
            os.mkfifo(fifo_path)
    else:
        os.mkfifo(fifo_path)

    # Start ffmpeg reading from the FIFO. Do not use shell operators; pass args directly.
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-re", "-i", "smptebars=duration=300:size=320x200:rate=30",
        "-f", "lavfi", "-re", "-i", "sine=frequency=1000:duration=300:sample_rate=48000",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-b:v", "180k", "-g", "60", "-keyint_min", "60",
        "-profile:v", "baseline", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "96k",
        "-vf", r"drawtext=fontfile=/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf: text='Local time %{localtime\: %Y/%m/%d %H.%M.%S} (%{n})': x=10: y=10: fontsize=16: fontcolor=white: box=1: boxcolor=0x00000099",
        "-f", "flv",
        fifo_path
    ]
    return sp.Popen(cmd)


def start_streamer():
    fifo_path = os.path.expanduser(PIPE_PATH)
    cmd = [
        "./_build/moxygen/samples/flv_streamer_client/moqflvstreamerclient",
        "-input_flv_file", fifo_path,
        "-connect_url", RELAY_URL,
        "--logging", "DBG1"
    ]
    return sp.Popen(cmd)


def start_receiver():
    # Create 10 receiver processes
    receivers = []
    for i in range(10):
        print(f"Starting receiver {i}")
        output_path = os.path.expanduser(f"~/Movies/moq-out-{i}.flv")
        cmd = [
            "./_build/moxygen/samples/flv_receiver_client/moqflvreceiverclient",
            "-connect_url", RELAY_URL,
            "--flv_outpath", output_path,
            "-stats_log_file", f"./client-{i}.log",
            "--logging", "DBG1"
        ]
        receivers.append(sp.Popen(cmd))
    return receivers


if __name__ == "__main__":
    # relay = start_relay_server()
    # time.sleep(2)  # Give the relay server some time to start
    video_source = start_video_source()
    time.sleep(1)  # Give the video source some time to start
    streamer = start_streamer()
    print("Streamer started, waiting before starting receivers...")
    receivers = start_receiver()

    try:
        # Keep the main thread alive while subprocesses run
        while True:
            pass
    except KeyboardInterrupt:
        print("Terminating processes...")
        video_source.terminate()
        streamer.terminate()
        for receiver in receivers:
            receiver.terminate()
        print("All processes terminated.")

    # Clean up the named pipe
    fifo_path = os.path.expanduser(PIPE_PATH)
    sp.run(["rm", fifo_path])

    # Test the output files
    for i in range(10):
        output_file = os.path.expanduser(f"~/Movies/moq-out-{i}.flv")
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            output_file
        ]
        result = sp.run(cmd, capture_output=True, text=True)
        duration = result.stdout.strip()
        print(f"Output file {output_file} duration: {duration} seconds")
