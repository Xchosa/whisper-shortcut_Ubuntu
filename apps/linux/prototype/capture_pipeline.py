"""GStreamer capture graph; live mode caps both WAV and inference audio upstream."""


def capture_description(live=False):
    if not live:
        return ('audiomixer name=mix ! audioconvert ! audioresample ! '
                'audio/x-raw,format=S16LE,rate=16000,channels=1 ! wavenc ! filesink name=output')
    # Fix mixer rate and buffer duration before the cap: 30,000 * 160 mono frames.
    # identity emits EOS before buffer 30,001, so both tee branches receive <=300s.
    return ('audiomixer name=mix output-buffer-duration=10000000 ! '
            'audio/x-raw,format=S16LE,rate=16000,channels=1 ! identity eos-after=30001 ! '
            'tee name=audio audio. ! queue ! wavenc ! filesink name=output '
            'audio. ! queue ! appsink name=live emit-signals=true sync=false max-buffers=8')
