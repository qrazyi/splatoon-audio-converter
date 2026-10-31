"""Conservative packaging-only exclusions for the unchanged Qt Widgets app.

Keep Python, NumPy, the original interface/font and Windows PCM audio backend.
Omit plugins used only for video, PDF, QML/virtual keyboards and 3D rendering.
Qt 6.12 uses Windows' system ICU API, not an unrelated bundled ICU data file.
"""
import re


def omit_runtime(relative):
    name = str(relative).replace("\\", "/").lower()
    leaf = name.rsplit("/", 1)[-1]
    return (
        bool(re.fullmatch(r"icu(?:dt|in|uc)\d*\.dll", leaf))
        or leaf == "opengl32sw.dll"
        or leaf in {"qt6pdf.dll", "qt6opengl.dll", "qt6virtualkeyboard.dll",
                    "qt6multimediawidgets.dll", "ffmpegmediaplugin.dll", "qpdf.dll"}
        or leaf.startswith(("qt6quick", "qt6qml"))
        or bool(re.fullmatch(r"(?:avcodec|avformat|avutil|swscale|swresample)-\d+\.dll", leaf))
        or "/plugins/platforminputcontexts/" in name
        or "/plugins/generic/" in name
        or ("/plugins/platforms/" in name and leaf not in {"qwindows.dll", "qoffscreen.dll"})
    )
