"""Opt-in GStreamer boundary check; five minutes of synthetic audio, no microphone."""
from pathlib import Path
import sys
import tempfile
import wave
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'apps/linux/prototype'))
from capture_pipeline import capture_description

Gst.init(None)
with tempfile.TemporaryDirectory(prefix='whisper-cap-') as directory:
    for rate in (16000, 44100, 48000):
        path = Path(directory) / 'test.wav'
        path.touch(mode=0o600, exist_ok=True)
        pipeline = Gst.parse_launch(
            f'audiotestsrc wave=silence num-buffers=20000 ! audio/x-raw,rate={rate},channels=1 ! '
            'audioconvert ! audioresample ! mix. ' + capture_description(True))
        pipeline.get_by_name('output').set_property('location', str(path))
        samples = [0]
        def consume(sink):
            sample = sink.emit('pull-sample')
            samples[0] += sample.get_buffer().get_size()
            return Gst.FlowReturn.OK
        pipeline.get_by_name('live').connect('new-sample', consume)
        try:
            pipeline.set_state(Gst.State.PLAYING)
            message = pipeline.get_bus().timed_pop_filtered(
                30 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            assert message and message.type == Gst.MessageType.EOS, 'capture EOS missing'
        finally:
            pipeline.set_state(Gst.State.NULL)
        with wave.open(str(path)) as audio:
            assert audio.getframerate() == 16000 and audio.getnchannels() == 1
            assert audio.getnframes() == 4800000, 'WAV must stop at 300 seconds'
            assert samples[0] == audio.getnframes() * 2, 'live and WAV branches differ'
        print(f'GStreamer {rate} Hz input: WAV and live PCM capped at exactly 300 seconds; EOS passed.')
