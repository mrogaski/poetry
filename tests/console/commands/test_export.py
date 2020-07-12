# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import shutil

import pytest

from cleo.testers import CommandTester

from poetry.factory import Factory
from poetry.repositories.legacy_repository import LegacyRepository
from poetry.repositories.legacy_repository import Page
from poetry.repositories.pool import Pool
from tests.helpers import get_package

from ..conftest import Application
from ..conftest import Locker
from ..conftest import Path


try:
    import urllib.parse as urlparse
except ImportError:
    import urlparse

PYPROJECT_CONTENT = """\
[tool.poetry]
name = "simple-project"
version = "1.2.3"
description = "Some description."
authors = [
    "Sébastien Eustace <sebastien@eustace.io>"
]
license = "MIT"

readme = "README.rst"

homepage = "https://python-poetry.org"
repository = "https://github.com/python-poetry/poetry"
documentation = "https://python-poetry.org/docs"

keywords = ["packaging", "dependency", "poetry"]

classifiers = [
    "Topic :: Software Development :: Build Tools",
    "Topic :: Software Development :: Libraries :: Python Modules"
]

# Requirements
[tool.poetry.dependencies]
python = "~2.7 || ^3.4"
foo = "^1.0"
bar = { version = "^1.1", optional = true }

[tool.poetry.extras]
feature_bar = ["bar"]
"""


@pytest.fixture
def poetry(repo, tmp_dir):
    with (Path(tmp_dir) / "pyproject.toml").open("w", encoding="utf-8") as f:
        f.write(PYPROJECT_CONTENT)

    p = Factory().create_poetry(Path(tmp_dir))

    locker = Locker(p.locker.lock.path, p.locker._local_config)
    locker.write()
    p.set_locker(locker)

    pool = Pool()
    pool.add_repository(repo)
    p.set_pool(pool)

    yield p


@pytest.fixture
def app(poetry):
    return Application(poetry)


class MockRepository(LegacyRepository):
    FIXTURES = Path(__file__).parent / "fixtures" / "export"

    def _get(self, endpoint):
        parts = endpoint.split("/")
        name = parts[1]

        fixture = self.FIXTURES / (name + ".html")
        if not fixture.exists():
            return

        with fixture.open(encoding="utf-8") as f:
            return Page(self._url + endpoint, f.read(), {})

    def _download(self, url, dest):
        filename = urlparse.urlparse(url).path.rsplit("/")[-1]
        filepath = self.FIXTURES.parent / "dists" / filename

        shutil.copyfile(str(filepath), dest)


def test_export_exports_requirements_txt_file_locks_if_no_lock_file(app, repo):
    command = app.find("export")
    tester = CommandTester(command)

    assert not app.poetry.locker.lock.exists()

    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    tester.execute("--format requirements.txt --output requirements.txt")

    requirements = app.poetry.file.parent / "requirements.txt"
    assert requirements.exists()

    with requirements.open(encoding="utf-8") as f:
        content = f.read()

    assert app.poetry.locker.lock.exists()

    expected = """\
foo==1.0.0
"""

    assert expected == content
    assert "The lock file does not exist. Locking." in tester.io.fetch_output()


def test_export_exports_requirements_txt_uses_lock_file(app, repo):
    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    command = app.find("lock")
    tester = CommandTester(command)
    tester.execute()

    assert app.poetry.locker.lock.exists()

    command = app.find("export")
    tester = CommandTester(command)

    tester.execute("--format requirements.txt --output requirements.txt")

    requirements = app.poetry.file.parent / "requirements.txt"
    assert requirements.exists()

    with requirements.open(encoding="utf-8") as f:
        content = f.read()

    assert app.poetry.locker.lock.exists()

    expected = """\
foo==1.0.0
"""

    assert expected == content
    assert "The lock file does not exist. Locking." not in tester.io.fetch_output()


def test_export_fails_on_invalid_format(app, repo):
    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    command = app.find("lock")
    tester = CommandTester(command)
    tester.execute()

    assert app.poetry.locker.lock.exists()

    command = app.find("export")
    tester = CommandTester(command)

    with pytest.raises(ValueError):
        tester.execute("--format invalid")


def test_export_prints_to_stdout_by_default(app, repo):
    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    command = app.find("lock")
    tester = CommandTester(command)
    tester.execute()

    assert app.poetry.locker.lock.exists()

    command = app.find("export")
    tester = CommandTester(command)

    tester.execute("--format requirements.txt")

    expected = """\
foo==1.0.0
"""

    assert expected == tester.io.fetch_output()


def test_export_includes_extras_by_flag(app, repo):
    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    command = app.find("lock")
    tester = CommandTester(command)
    tester.execute()

    assert app.poetry.locker.lock.exists()

    command = app.find("export")
    tester = CommandTester(command)

    tester.execute("--format requirements.txt --extras feature_bar")

    expected = """\
bar==1.1.0
foo==1.0.0
"""

    assert expected == tester.io.fetch_output()


def test_export_includes_private_repository(app, repo):
    source = MockRepository(
        "mirror",
        "https://repo.example.com/api/pypi/public-mirror-pypi/simple",
        disable_cache=True,
    )
    app.poetry.pool.add_repository(source)

    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    command = app.find("lock")
    tester = CommandTester(command)
    tester.execute()

    assert app.poetry.locker.lock.exists()

    command = app.find("export")
    tester = CommandTester(command)

    tester.execute("--format requirements.txt --without-hashes")

    expected = """\
foo==1.0.0
"""

    assert expected == tester.io.fetch_output()


def test_export_includes_secondary_private_repository(app, repo):
    source = MockRepository(
        "mirror",
        "https://repo.example.com/api/pypi/public-mirror-pypi/simple",
        disable_cache=True,
    )
    app.poetry.pool.add_repository(source, secondary=True)

    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    command = app.find("lock")
    tester = CommandTester(command)
    tester.execute()

    assert app.poetry.locker.lock.exists()

    command = app.find("export")
    tester = CommandTester(command)

    tester.execute("--format requirements.txt --without-hashes")

    expected = """\
--extra-index-url https://repo.example.com/api/pypi/local-pypi/simple

foo==1.0.0
"""

    assert expected == tester.io.fetch_output()


def test_export_includes_default_private_repository(app, repo):
    source = MockRepository(
        "mirror",
        "https://repo.example.com/api/pypi/public-mirror-pypi/simple",
        disable_cache=True,
    )
    app.poetry.pool.add_repository(source, default=True)

    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    command = app.find("lock")
    tester = CommandTester(command)
    tester.execute()

    assert app.poetry.locker.lock.exists()

    command = app.find("export")
    tester = CommandTester(command)

    tester.execute("--format requirements.txt --without-hashes")

    expected = """\
--index-url https://repo.example.com/api/pypi/public-mirror-pypi/simple

foo==1.0.0
"""

    assert expected == tester.io.fetch_output()


def test_export_includes_default_private_repository_and_other(app, repo):
    source = MockRepository(
        "mirror",
        "https://repo.example.com/api/pypi/public-mirror-pypi/simple",
        disable_cache=True,
    )
    app.poetry.pool.add_repository(source, default=True)

    other = MockRepository(
        "local",
        "https://repo.example.com/api/pypi/local-pypi/simple",
        disable_cache=True,
    )
    app.poetry.pool.add_repository(other)

    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    command = app.find("lock")
    tester = CommandTester(command)
    tester.execute()

    assert app.poetry.locker.lock.exists()

    command = app.find("export")
    tester = CommandTester(command)

    tester.execute("--format requirements.txt --without-hashes")

    expected = """\
--index-url https://repo.example.com/api/pypi/public-mirror-pypi/simple

foo==1.0.0
"""

    assert expected == tester.io.fetch_output()


def test_export_includes_default_private_repository_and_secondary(app, repo):
    source = MockRepository(
        "mirror",
        "https://repo.example.com/api/pypi/public-mirror-pypi/simple",
        disable_cache=True,
    )
    app.poetry.pool.add_repository(source, default=True)

    other = MockRepository(
        "local",
        "https://repo.example.com/api/pypi/local-pypi/simple",
        disable_cache=True,
    )
    app.poetry.pool.add_repository(other, secondary=True)

    repo.add_package(get_package("foo", "1.0.0"))
    repo.add_package(get_package("bar", "1.1.0"))

    command = app.find("lock")
    tester = CommandTester(command)
    tester.execute()

    assert app.poetry.locker.lock.exists()

    command = app.find("export")
    tester = CommandTester(command)

    tester.execute("--format requirements.txt --without-hashes")

    expected = """\
--index-url https://repo.example.com/api/pypi/public-mirror-pypi/simple
--extra-index-url https://repo.example.com/api/pypi/local-pypi/simple

foo==1.0.0
"""

    assert expected == tester.io.fetch_output()
