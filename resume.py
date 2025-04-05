#!/usr/bin/env python3
import argparse
import base64
import itertools
import logging
import os
import shutil
import subprocess
import sys
import tempfile

import markdown

HTML_TEMPLATE = """
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        {css}
    </style>
</head>
<body>
    <div id="resume">
        {body}
    </div>
</body>
</html>
"""


CHROME_GUESSES_MACOS = (
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

# https://stackoverflow.com/a/40674915/409879
CHROME_GUESSES_WINDOWS = (
    # Windows 10
    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
)

# look for binaries in PATH
CHROME_GUESSES_LINUX = (
    "thorium",
    "google-chrome",
    "chrome",
    "chromium",
    "chromium-browser",
    "microsoft-edge-stable",
    "opera"
)

def guess_chrome_path() -> str:
    if sys.platform == "darwin":
        guesses = CHROME_GUESSES_MACOS
    elif sys.platform == "win32":
        guesses = CHROME_GUESSES_WINDOWS
    else:
        guesses = CHROME_GUESSES_LINUX
    for guess in guesses:
        path = shutil.which(guess)
        if path:
            logging.info("Found some 'Chrome' at  [%s ]", path)
            return path
    raise ValueError("Could not find Chrome. Please set CHROME_PATH.")


def get_title(md: str) -> str:
    """
    Return the contents of the first markdown heading in md, which we
    assume to be the title of the document.
    """
    for line in md.splitlines():
        if line[0] == "#":
            return line.strip("#").strip()
    raise ValueError("Cannot find any lines that look like markdown headings")


def make_html(md: str, title: str, css_prefix: str) -> str:
    """
    Compile md to HTML

    """
    try:
        with open("css/font-awesome.4.7.0.min.css") as file:
            css1 = file.read()
        with open(css_prefix + ".css") as file:
            css2 = file.read()
        css = css1 + css2
    except FileNotFoundError:
        print(prefix + ".css not found. Output will by unstyled.")
        css = ""

    return HTML_TEMPLATE.format(
        title=title,
        css=css,
        body = markdown.markdown(md, extensions=["smarty"])
    )


def write_pdf(html: str, prefix: str = "resume", chrome: str = "") -> None:
    """
    Write html to prefix.pdf
    """
    chrome = chrome or guess_chrome_path()

    html64 = base64.b64encode(html.encode("utf-8"))
    options = [
        "--headless",
        "--print-to-pdf-no-header",
        "--enable-logging=stderr",
        "--log-level=2",
    ]
    # https://bugs.chromium.org/p/chromium/issues/detail?id=737678
    if sys.platform == "win32":
        options.append("--disable-gpu")

    tmpdir = tempfile.TemporaryDirectory(prefix="resume.md_")
    options.append(f"--crash-dumps-dir={tmpdir.name}")
    options.append(f"--user-data-dir={tmpdir.name}")
    try:
        subprocess.run(
            [
                chrome,
                *options,
                f"--print-to-pdf={prefix}.pdf",
                "data:text/html;base64," + html64.decode("utf-8"),
            ],
            check=True,
        )
        logging.info(f"Wrote {prefix}.pdf")
    except subprocess.CalledProcessError as exc:
        if exc.returncode == -6:
            logging.warning(
                "Chrome died with <Signals.SIGABRT: 6> "
                f"but you may find {prefix}.pdf was created successfully."
            )
        else:
            raise exc
    finally:
        # We use this try-finally rather than TemporaryDirectory''s context
        # manager to be able to catch the exception caused by
        # https://bugs.python.org/issue26660 on Windows
        try:
            shutil.rmtree(tmpdir.name)
        except PermissionError as exc:
            logging.warning(f"Could not delete {tmpdir.name}")
            logging.info(exc)

def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "file",
        help="markdown input file [resume.md]",
        default="resume.md",
        nargs="?",
    )
    parser.add_argument(
        "--css",
        type=str,
        help="Provide custom css file",
        default="css/" + os.path.basename(__file__).split('.')[0]
    )
    parser.add_argument(
        "--no-html",
        help="Do not write html output",
        action="store_true",
    )
    parser.add_argument(
        "--no-pdf",
        help="Do not write pdf output",
        action="store_true",
    )
    parser.add_argument(
        "--chrome-path",
        help="Path to Chrome or Chromium executable",
    )

    parser.add_argument("-q", "--quiet", action="store_true")
    return parser.parse_args()

def write_resume(args):
    with open(args.file) as mdfp:
        md = mdfp.read()

    title = get_title(md)
    html = make_html(md, title = title, css_prefix=args.css)
    prefix = title.replace(' ', '_') + "_CV"

    if not args.no_html:
        with open(prefix + ".html", "w") as htmlfp:
            htmlfp.write(html)
            logging.info(f"Wrote {htmlfp.name}")

    if not args.no_pdf:
        write_pdf(html, prefix=prefix, chrome=args.chrome_path)

if __name__ == "__main__":
    args = parse_command_line()

    if args.quiet:
        logging.basicConfig(level=logging.WARN, format="%(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    write_resume(args)

