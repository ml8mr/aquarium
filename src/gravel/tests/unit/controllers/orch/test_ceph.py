# project aquarium's backend
# Copyright (C) 2021 SUSE, LLC.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

import json
import os
import pytest

from typing import Any, Callable, Dict, Generator
from pyfakefs import fake_filesystem  # pyright: reportMissingTypeStubs=false
from pytest_mock import MockerFixture

from gravel.controllers.orch.ceph import Mgr, Mon

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
TEST_DIR = os.path.join(os.path.dirname(__file__), '../../../')


def test_ceph_conf(fs: fake_filesystem.FakeFilesystem):
    # default location
    fs.add_real_file(  # pyright: reportUnknownMemberType=false
        os.path.join(TEST_DIR, 'data/default_ceph.conf'),
        target_path='/etc/ceph/ceph.conf'
    )
    Mgr()
    Mon()

    # custom location
    conf_file = '/foo/bar/baz.conf'
    fs.add_real_file(
        os.path.join(TEST_DIR, 'data/default_ceph.conf'),
        target_path=conf_file
    )
    Mgr(conf_file=conf_file)
    Mon(conf_file=conf_file)

    # invalid location
    conf_file = "missing.conf"
    with pytest.raises(FileNotFoundError, match=conf_file):
        Mgr(conf_file=conf_file)
        Mon(conf_file=conf_file)


def test_mon_df(
    ceph_conf_file_fs: Generator[fake_filesystem.FakeFilesystem, None, None],
    mocker: MockerFixture,
    get_data_contents: Callable[[str, str], str]
):
    mon = Mon()
    mon.call = mocker.MagicMock(
        return_value=json.loads(get_data_contents(DATA_DIR, 'mon_df_raw.json'))
    )

    res = mon.df()
    assert res.stats.total_bytes == 0


def test_get_osdmap(
    ceph_conf_file_fs: Generator[fake_filesystem.FakeFilesystem, None, None],
    mocker: MockerFixture,
    get_data_contents: Callable[[str, str], str]
):
    mon = Mon()
    mon.call = mocker.MagicMock(
        return_value=json.loads(
            get_data_contents(DATA_DIR, 'mon_osdmap_raw.json'))
    )
    res = mon.get_osdmap()
    assert res.epoch == 4


def test_get_pools(
    ceph_conf_file_fs: Generator[fake_filesystem.FakeFilesystem, None, None],
    mocker: MockerFixture,
    get_data_contents: Callable[[str, str], str]
):
    mon = Mon()
    mon.call = mocker.MagicMock(
        return_value=json.loads(
            get_data_contents(DATA_DIR, 'mon_osdmap_raw.json'))
    )
    res = mon.get_pools()
    assert len(res) == 0


def test_set_pool_size(
    ceph_conf_file_fs: Generator[fake_filesystem.FakeFilesystem, None, None],
    mocker: MockerFixture
):
    def argscheck(cls: Any, args: Dict[str, Any]) -> Any:
        assert "prefix" in args
        assert "pool" in args
        assert "var" in args
        assert "val" in args
        assert args["prefix"] == "osd pool set"
        assert args["pool"] == "foobar"
        assert args["var"] in ["size", "min_size"]

        if args["var"] == "size":
            assert args["val"] == "2"
            assert "i_really_mean_it" not in args
        else:
            assert args["var"] == "min_size"
            assert args["val"] == "1"

    mocker.patch.object(
        Mon, "call", new=argscheck  # type:ignore
    )
    mon = Mon()
    mon.set_pool_size("foobar", 2)
