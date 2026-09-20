"""Process-wide Qt WebEngine configuration; import before any PySide module."""
import os


STABLE_CHROMIUM_FLAGS = (
    '--no-proxy-server',
    '--disable-gpu',
    '--use-gl=angle',
    '--use-angle=swiftshader',
    '--disable-features=DirectComposition,Vulkan,WebGPU',
)


def configure_webengine():
    flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '')
    for flag in STABLE_CHROMIUM_FLAGS:
        if flag not in flags:
            flags = f'{flags} {flag}'.strip()
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = flags
