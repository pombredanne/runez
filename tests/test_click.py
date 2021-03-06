# -*- coding: utf-8 -*-

"""
Test click related methods
"""

from mock import patch

import runez


def test_settings():
    s = runez.click.settings(foo="bar")
    assert len(s) == 3
    assert s["epilog"] == "Test click related methods"
    assert s["foo"] == "bar"
    assert s["context_settings"] == dict(help_option_names=["-h", "--help"], max_content_width=140)

    s = runez.click.settings(help="-h --help --explain")
    assert s["context_settings"]["help_option_names"] == ["-h", "--help", "--explain"]


def test_command():
    with patch("runez.click.click") as fake_click:
        fake_click.command = FakeClick
        fake_click.group = FakeClick
        assert runez.click.command().epilog == "Test click related methods"
        assert runez.click.group().epilog == "Test click related methods"


def test_missing_click():
    # When click is not installed, we don't crash, we just don't decorate the underlying functions
    assert runez.click.click is None
    assert runez.click.debug() is runez.click.debug
    assert runez.click.dryrun() is runez.click.dryrun
    assert runez.click.log() is runez.click.log
    assert runez.click.log() is runez.click.log


class FakeClick(object):

    default = None
    epilog = None
    help = None
    metavar = None
    required = None
    show_default = None
    version = None

    def __init__(self, *args, **kwargs):
        self.args = list(args)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __call__(self, func):
        self.func = func
        return self

    @classmethod
    def get_decorated(cls, func, *args, **kwargs):
        return func(*args, **kwargs)(func)


def test_with_click():
    # When click is available, we properly decorate
    with patch("runez.click.click") as fake_click:
        fake_click.option = FakeClick
        fake_click.version_option = FakeClick

        def some_function():
            """Some help ☘."""
            return runez.click.option(some_function)

        decorated = FakeClick.get_decorated(some_function)
        assert isinstance(decorated, FakeClick)
        assert decorated.args == ["--some-function"]
        assert decorated.default is None
        assert decorated.help == "Some help ☘."
        assert decorated.metavar == "SOME_FUNCTION"
        assert decorated.required is False
        assert decorated.show_default is True

        config = FakeClick.get_decorated(runez.click.config)
        assert isinstance(config, FakeClick)
        assert config.args == ["--config"]
        assert not config.default

        debug = FakeClick.get_decorated(runez.click.debug)
        assert isinstance(debug, FakeClick)
        assert debug.args == ["--debug"]
        assert not debug.default

        dryrun = FakeClick.get_decorated(runez.click.dryrun, "-n")
        assert isinstance(dryrun, FakeClick)
        assert dryrun.args == ["--dryrun", "-n"]

        log = FakeClick.get_decorated(runez.click.log, "-l", default="some-place")
        assert isinstance(log, FakeClick)
        assert log.args == ["--log", "-l"]
        assert log.default == "some-place"
        assert log.help == "Override log file location."
        assert log.required is False
        assert log.show_default is False
        assert log.metavar == "PATH"

        version = FakeClick.get_decorated(runez.click.version, "-v")
        assert isinstance(version, FakeClick)
        assert version.args == ["-v"]

        version = FakeClick.get_decorated(runez.click.version, package="runez")
        assert isinstance(version, FakeClick)
        assert version.version == runez.get_version(runez)
