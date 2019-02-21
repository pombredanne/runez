import logging
import os
import sys

import pytest
from mock import patch

import runez


LOG = logging.getLogger(__name__)


def test_logspec(isolated_log_setup):
    s1 = runez.LogSpec(runez.log._default_spec)
    s2 = runez.LogSpec(runez.log._default_spec)
    assert s1 == s2
    assert s1.appname == "pytest"
    assert s1.timezone == "UTC"
    assert s1.should_log_to_file
    assert s1.usable_location() == "/tmp/pytest.log"

    # No appname -> can't determine a usable location anymore
    s1.appname = None
    assert s1.should_log_to_file
    assert s1.usable_location() is None

    s1.set(appname="testing", timezone=None, locations=[s1.tmp])
    assert s1.appname == "testing"
    assert s1.timezone is None
    assert s1.usable_location() == "/tmp/testing.log"
    assert s1 != s2

    # Empty string custom location just disables file logging
    s1.custom_location = ""
    assert not s1.should_log_to_file
    assert s1.usable_location() is None

    # No basename, and custom location points to folder -> not usable
    s1.appname = None
    s1.custom_location = "/tmp"
    assert s1.should_log_to_file
    assert s1.usable_location() is None

    # Restore from other spec
    s1.set(s2)
    assert s1 == s2

    with pytest.raises(ValueError):
        s1.set(not_valid="this is not a field of LogSpec")

    with pytest.raises(ValueError):
        s1.set("hello")

    with pytest.raises(ValueError):
        s1.set(s2, "hello")

    with pytest.raises(ValueError):
        s1.set(s2, timezone="hello")


def test_setup(temp_log):
    fmt = "%(asctime)s %(context)s%(levelname)s - %(message)s"
    assert runez.log.is_using_format("", fmt) is False
    assert runez.log.is_using_format("%(lineno)d", fmt) is False
    assert runez.log.is_using_format("%(context)s", fmt) is True
    assert runez.log.is_using_format("%(context)s %(lineno)d", fmt) is True
    assert runez.log.is_using_format("%(context)s", "") is False

    # signum=None is equivalent to disabling faulthandler
    runez.log.enable_faulthandler(signum=None)
    assert runez.log.faulthandler_signum is None
    # We didn't call setup, so enabling faulthandler will do nothing
    runez.log.enable_faulthandler()
    assert runez.log.faulthandler_signum is None

    cwd = os.getcwd()
    assert not runez.DRYRUN
    with runez.TempFolder(dryrun=False):
        runez.log.setup(dryrun=True, level=logging.INFO)

        # Auto-debug on dryrun
        logging.debug("hello")
        assert "hello" in temp_log.logged.stderr

        with pytest.raises(Exception):
            # SHouldn't call setup() twice
            runez.log.setup()

        if runez.log.faulthandler:
            # Available only in python3
            runez.log.enable_faulthandler()
            assert runez.log.faulthandler_signum

    assert not runez.DRYRUN
    assert os.getcwd() == cwd


def test_default(temp_log):
    runez.log.context.set_global(version="1.0")
    runez.log.context.add_global(worker="mark")
    runez.log.context.add_threadlocal(worker="joe", foo="bar")
    runez.log.context.set_threadlocal(worker="joe")
    runez.log.setup()

    assert temp_log.logfile == "pytest.log"
    assert "Logging to" in temp_log.stderr
    assert "pid %s" % os.getpid() in temp_log.stderr
    logging.info("hello")

    temp_log.expect_logged("UTC [[version=1.0,worker=joe]] INFO - hello")
    assert "INFO hello" in temp_log.stderr


def test_level(temp_log):
    runez.log.setup(file_format=None, level=logging.INFO)

    assert not temp_log.logged
    assert temp_log.logfile is None
    logging.debug("debug msg")
    logging.info("info msg")
    assert "debug msg" not in temp_log.stderr
    assert "info msg" in temp_log.stderr


def test_console(temp_log):
    logger = logging.getLogger("runez")
    old_level = logger.level
    runez.log.setup(custom_location="", greeting=["{actual_location}, {pid}", ":: argv: {argv}"])

    assert temp_log.logfile is None
    assert "DEBUG Not logging to file, pid " in temp_log.stderr
    assert ":: argv: " in temp_log.stderr
    logger.info("hello")
    assert "INFO hello" in temp_log.stderr

    temp_log.logged.clear()
    runez.log.silence(runez)
    logger.info("hello")
    assert not temp_log.logged

    logger.setLevel(old_level)


def test_no_context(temp_log):
    runez.log.context.set_global(version="1.0")
    runez.log.spec.set(timezone="", file_format="%(asctime)s [%(threadName)s] %(timezone)s %(levelname)s - %(message)s")
    runez.log.setup()
    logging.info("hello")
    temp_log.expect_logged("[MainThread] INFO - hello")


def test_context(temp_log):
    runez.log.spec.locations = None
    runez.log.spec.console_stream = sys.stderr
    runez.log.spec.console_format = "%(name)s %(timezone)s %(context)s%(levelname)s - %(message)s"
    runez.log.setup(greeting=None)

    assert temp_log.logfile is None

    # Edge case: verify adding/removing ends up with empty context
    runez.log.context.add_global(x="y")
    runez.log.context.remove_global("x")
    assert not runez.log.context.has_global()

    runez.log.context.add_threadlocal(x="y")
    runez.log.context.remove_threadlocal("x")
    assert not runez.log.context.has_threadlocal()

    # Add a couple global/thread context values
    runez.log.context.set_global(version="1.0", name="foo")
    runez.log.context.add_threadlocal(worker="susan", a="b")
    logging.info("hello")
    assert temp_log.stderr.pop(strip=True) == "test_logsetup UTC [[a=b,name=foo,version=1.0,worker=susan]] INFO - hello"

    # Remove them one by one
    runez.log.context.remove_threadlocal("a")
    logging.info("hello")
    assert temp_log.stderr.pop(strip=True) == "test_logsetup UTC [[name=foo,version=1.0,worker=susan]] INFO - hello"

    runez.log.context.remove_global("name")
    logging.info("hello")
    assert temp_log.stderr.pop(strip=True) == "test_logsetup UTC [[version=1.0,worker=susan]] INFO - hello"

    runez.log.context.clear_threadlocal()
    logging.info("hello")
    assert temp_log.stderr.pop(strip=True) == "test_logsetup UTC [[version=1.0]] INFO - hello"

    runez.log.context.clear_global()
    logging.info("hello")
    assert temp_log.stderr.pop(strip=True) == "test_logsetup UTC INFO - hello"

    assert not runez.log.context.has_global()
    assert not runez.log.context.has_threadlocal()


def test_convenience(temp_log):
    fmt = "%(name)s f:%(filename)s mod:%(module)s func:%(funcName)s %(levelname)s %(message)s "
    fmt += " path:%(pathname)s"
    runez.log.setup(console_format=fmt, file_format=None)

    assert temp_log.logfile is None
    runez.write("some-file", "some content", logger=logging.info)
    logging.info("hello")
    logging.exception("oops")

    assert "runez.file f:file.py mod:file func:write INFO Writing 12 bytes" in temp_log.stderr
    assert "test_logsetup f:test_logsetup.py mod:test_logsetup func:test_convenience INFO hello" in temp_log.stderr
    assert "test_logsetup f:test_logsetup.py mod:test_logsetup func:test_convenience ERROR oops" in temp_log.stderr
    temp_log.stderr.clear()

    runez.write("some-file", "some content", logger=LOG.info)
    LOG.info("hello")
    LOG.exception("oops")
    assert "test_logsetup f:file.py mod:file func:write INFO Writing 12 bytes" in temp_log.stderr
    assert "test_logsetup f:test_logsetup.py mod:test_logsetup func:test_convenience INFO hello" in temp_log.stderr
    assert "test_logsetup f:test_logsetup.py mod:test_logsetup func:test_convenience ERROR oops" in temp_log.stderr


def test_auto_location_not_writable(temp_log):
    with patch("runez.path.os.access", return_value=False):
        runez.log.setup(console_format="%(name)s f:%(filename)s mod:%(module)s func:%(funcName)s %(levelname)s - %(message)s")

        assert "runez.logsetup f:system.py mod:system func:abort DEBUG" in temp_log.stderr
        assert "No usable log locations" in temp_log.stderr

        assert runez.log.file_handler is None


def test_custom_location_not_writable(temp_log):
    runez.log.setup(
        custom_location="/dev/null/somewhere.log",
    )

    assert "DEBUG Can't create folder /dev/null" in temp_log.stderr
    assert "DEBUG Can't log to /dev/null/somewhere.log" in temp_log.stderr

    assert runez.log.file_handler is None