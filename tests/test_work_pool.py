"""Work pool tests with a fake engine (no 7-Zip); helpers in fake_archives.py."""

import os

import pytest

from complex_unzip_tool_v2.modules import multipart_assembly as ma
from complex_unzip_tool_v2.modules import work_pool as wp

from fake_archives import (
    FakeEngine,
    archive,
    deleted,
    output_files,
    run_pool,
    uncloak_suffix,
    volume,
    write,
    Remover,
)


# ------------------------------
# Input roots
# ------------------------------


def test_input_roots_merge_nested_roots(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    single = tmp_path / "c" / "x.7z"
    write(single, archive({}))
    roots = wp.group_input_roots(
        [str(tmp_path / "a"), str(tmp_path / "a" / "b"), str(single)]
    )
    assert roots == [
        (str(tmp_path / "a"), [str(tmp_path / "a"), str(tmp_path / "a" / "b")]),
        (str(tmp_path / "c"), [str(single)]),
    ]


@pytest.mark.parametrize(
    "name, folder",
    [
        ("A.7z", "A"),
        ("X.7z.001", "X"),
        ("X.part1.rar", "X"),
        ("X.tar.gz.001", "X"),
        ("X.zipx", "X"),
        ("X.zx01", "X"),
        ("X.r00", "X"),
        ("photos.2024.zip", "photos.2024"),
        ("notes.txt", "notes.txt"),
    ],
)
def test_derive_folder_name(name, folder):
    assert wp.derive_folder_name(name) == folder


# ------------------------------
# Containers
# ------------------------------


def test_container_contents_reach_the_output_and_source_is_deleted(tmp_path):
    write(tmp_path / "A.7z", archive({"a.txt": "hello", "sub/b.txt": "b"}))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["a.txt", "sub/b.txt"]
    assert deleted(result) == ["A.7z"]
    assert result.unresolved == []
    assert not os.path.exists(result.work_dir)


def test_readme_next_to_an_archive_is_left_in_place(tmp_path):
    write(tmp_path / "A.7z", archive({"a.txt": "hello"}))
    write(tmp_path / "readme.txt", "keep me")
    result, remover = run_pool(tmp_path)
    assert (tmp_path / "readme.txt").exists()
    assert output_files(tmp_path) == ["a.txt"]
    assert deleted(result) == ["A.7z"]
    assert [i.state for i in result.items if i.path.endswith("readme.txt")] == [
        wp.State.KEPT
    ]


def test_nested_container_is_opened_in_the_next_round(tmp_path):
    events = []
    write(tmp_path / "A.7z", archive({"B.zip": archive({"c.txt": "c"}), "r.txt": "r"}))
    run_pool(tmp_path, emit=events.append)
    assert output_files(tmp_path) == ["B/c.txt", "r.txt"]
    opened = [e.item.path for e in events if isinstance(e, wp.ItemOpened)]
    rounds = [e.number for e in events if isinstance(e, wp.RoundStarted)]
    assert [os.path.basename(p) for p in opened] == ["A.7z", "B.zip"]
    assert rounds[:2] == [1, 2]


def test_nested_archive_kept_as_output_when_removal_fails(tmp_path):
    write(tmp_path / "A.7z", archive({"B.zip": archive({"c.txt": "c"})}))
    run_pool(tmp_path, remove=Remover(fail_on={"B.zip"}))
    assert output_files(tmp_path) == ["B.zip", "B/c.txt"]


def test_password_failed_nested_archive_is_preserved_and_source_kept(tmp_path):
    write(tmp_path / "A.7z", archive({"inner.rar": archive({"x": "x"}, password="zz")}))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["inner.rar"]
    assert deleted(result) == []
    assert [(os.path.basename(i.path), i.reason) for i in result.unresolved] == [
        ("inner.rar", "password")
    ]


def test_container_password_prompt(tmp_path):
    engine = FakeEngine()
    asked = []

    def prompt(path):
        asked.append(os.path.basename(path))
        return "secret"

    write(tmp_path / "A.7z", archive({"a.txt": "a"}, password="secret"))
    result, _ = run_pool(tmp_path, engine=engine, prompt=prompt)
    assert asked == ["A.7z"]
    assert engine.remembered == ["secret"]
    assert output_files(tmp_path) == ["a.txt"]
    opened = [i for i in result.items if i.path.endswith("A.7z")][0]
    assert opened.password_ref == "entered"


def test_skip_all_stops_further_prompts(tmp_path):
    asked = []

    def prompt(path):
        asked.append(os.path.basename(path))
        return wp.SKIP_ALL

    write(tmp_path / "A.7z", archive({"a": "a"}, password="p1"))
    write(tmp_path / "B.7z", archive({"b": "b"}, password="p2"))
    run_pool(tmp_path, prompt=prompt)
    assert asked == ["A.7z"]


def test_empty_archive_keeps_its_source(tmp_path):
    write(tmp_path / "A.7z", archive({}))
    result, remover = run_pool(tmp_path)
    assert deleted(result) == []
    assert [i.reason for i in result.unresolved] == ["empty"]


def test_broken_source_archive_is_reported(tmp_path):
    write(tmp_path / "bad.7z", {"kind": "broken"})
    result, remover = run_pool(tmp_path)
    assert [i.reason for i in result.unresolved] == ["not a valid archive"]
    assert (tmp_path / "bad.7z").exists() and deleted(result) == []


def test_depth_limit(tmp_path):
    write(
        tmp_path / "A.7z",
        archive({"B.zip": archive({"C.zip": archive({"deep.txt": "d"})})}),
    )
    result, remover = run_pool(tmp_path, max_depth=1)
    assert output_files(tmp_path) == ["B/C.zip"]
    assert [i.reason for i in result.unresolved] == ["max depth"]
    assert deleted(result) == []


def test_failed_move_keeps_work_dir_and_source(tmp_path):
    write(tmp_path / "A.7z", archive({"movie.mp4": "m", "ok.txt": "o"}))

    def mover(src, dst):
        if src.endswith("movie.mp4"):
            raise OSError("path too long")
        os.replace(src, dst)

    result, remover = run_pool(tmp_path, mover=mover)
    assert result.work_dir_kept and os.path.isdir(result.work_dir)
    assert deleted(result) == []
    assert [i.reason for i in result.unresolved] == ["move failed"]


# ------------------------------
# Multipart sets
# ------------------------------


def test_reproduction_cross_container_cloaked_volumes(tmp_path):
    calls = []
    events = []
    engine = FakeEngine(passwords=["pw1"])
    write(tmp_path / "A.7z", archive({"X.7z.002": volume("S1", 2, 2)}, "pw1"))
    write(
        tmp_path / "B.rar",
        archive({"X.7z.001删掉": volume("S1", 1, 2, files={"movie.mp4": "m"})}, "pw1"),
    )
    result, remover = run_pool(
        tmp_path, engine=engine, uncloak=uncloak_suffix(calls), emit=events.append
    )
    assert output_files(tmp_path) == ["X/movie.mp4"]
    assert deleted(result) == ["A.7z", "B.rar"]
    assert result.unresolved == []
    assert ("X.7z.001删掉", False) in calls
    assembled = [e for e in events if isinstance(e, wp.SetAssembled)]
    assert len(assembled) == 1
    volumes = assembled[0].volumes
    assert [v.original_name for v in volumes] == ["X.7z.001删掉", None]
    sources = [os.path.basename(result.item(v.parents[0]).path) for v in volumes]
    assert sources == ["B.rar", "A.7z"]


def test_missing_volume_hidden_in_another_set(tmp_path):
    write(tmp_path / "X.7z.001", volume("S1", 1, 2, files={"a.txt": "a"}))
    write(
        tmp_path / "Y.part1.rar",
        volume("Y", 1, 2, files={"X.7z.002": volume("S1", 2, 2)}),
    )
    write(tmp_path / "Y.part2.rar", volume("Y", 2, 2))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["a.txt"]
    assert deleted(result) == ["X.7z.001", "Y.part1.rar", "Y.part2.rar"]
    assert result.unresolved == []


def test_two_sets_share_a_name(tmp_path):
    write(tmp_path / "A.7z", archive({"X.7z.001": volume("S1", 1, 2, {"a": "a"})}))
    write(tmp_path / "B.7z", archive({"X.7z.002": volume("S2", 2, 2)}))
    write(tmp_path / "C.7z", archive({"X.7z.001": volume("S2", 1, 2, {"c": "c"})}))
    write(tmp_path / "D.7z", archive({"X.7z.002": volume("S1", 2, 2)}))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["X/a", "X/c"]
    assert deleted(result) == ["A.7z", "B.7z", "C.7z", "D.7z"]


def test_search_stops_at_the_input_root(tmp_path):
    root = tmp_path / "in"
    write(root / "X.7z.001", volume("S1", 1, 2, {"a": "a"}))
    write(tmp_path / "X.7z.002", volume("S1", 2, 2))
    result, remover = run_pool(root)
    assert [os.path.basename(i.path) for i in result.unresolved] == ["X.7z.001"]
    assert (root / "X.7z.001").exists() and (tmp_path / "X.7z.002").exists()
    assert deleted(result) == []


def test_unscanned_file_on_disk_is_not_used(tmp_path):
    write(tmp_path / "X.7z.001", volume("S1", 1, 2, {"a": "a"}))
    write(tmp_path / "old" / "X.7z.002", volume("S1", 2, 2))
    result, _ = run_pool(tmp_path, sources=[str(tmp_path / "X.7z.001")])
    assert [os.path.basename(i.path) for i in result.unresolved] == ["X.7z.001"]
    assert (tmp_path / "old" / "X.7z.002").exists()


def test_identical_duplicate_volume_does_not_pin_its_source(tmp_path):
    second = volume("S1", 2, 2)
    write(
        tmp_path / "A.7z",
        archive({"X.7z.001": volume("S1", 1, 2, {"f": "f"}), "X.7z.002": second}),
    )
    write(tmp_path / "B.7z", archive({"X.7z.002": second}))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["X/f"]
    assert deleted(result) == ["A.7z", "B.7z"]
    assert result.unresolved == []


def test_non_chosen_same_name_volume_next_to_primary(tmp_path):
    write(tmp_path / "X.7z.001", volume("S1", 1, 2, {"f": "f"}))
    write(tmp_path / "X.7z.002", volume("S2", 2, 2))
    write(tmp_path / "C.7z", archive({"X.7z.002": volume("S1", 2, 2)}))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["f"]
    assert deleted(result) == ["C.7z", "X.7z.001"]
    assert (tmp_path / "X.7z.002").exists()
    assert [os.path.basename(i.path) for i in result.unresolved] == ["X.7z.002"]


def test_spanned_zip_that_failed_as_a_container_is_assembled(tmp_path):
    write(tmp_path / "X.zip", volume("Z", 1, 2, {"z.txt": "z"}, alone="unsupported"))
    write(tmp_path / "Z.7z", archive({"X.z01": volume("Z", 2, 2)}))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["z.txt"]
    assert deleted(result) == ["X.zip", "Z.7z"]
    assert result.unresolved == []


def test_failed_set_volumes_are_preserved_together(tmp_path):
    write(tmp_path / "A.7z", archive({"X.7z.001": volume("S1", 1, 2, {"f": "f"})}))
    write(tmp_path / "B.7z", archive({"X.7z.002": volume("S2", 2, 2)}))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["X.7z.001", "X.7z.002"]
    assert deleted(result) == []


def test_source_volumes_return_home_after_a_failed_attempt(tmp_path):
    relocations = wp.MemoryRelocationLog()
    write(tmp_path / "s1" / "X.7z.001", volume("S1", 1, 2, {"f": "f"}))
    write(tmp_path / "s2" / "X.7z.002", volume("S2", 2, 2))
    run_pool(tmp_path, relocations=relocations)
    assert (tmp_path / "s1" / "X.7z.001").exists()
    assert (tmp_path / "s2" / "X.7z.002").exists()
    assert relocations.entries == {}
    assert relocations.recorded  # the moves were logged while they lasted


def test_source_volumes_deleted_from_their_own_folders_after_success(tmp_path):
    write(tmp_path / "s1" / "X.7z.001", volume("S1", 1, 2, {"f": "f"}))
    write(tmp_path / "s2" / "X.7z.002", volume("S1", 2, 2))
    result, _ = run_pool(tmp_path)
    assert sorted(result.deleted_sources) == sorted(
        [str(tmp_path / "s1" / "X.7z.001"), str(tmp_path / "s2" / "X.7z.002")]
    )
    assert not (tmp_path / "s1").exists() and not (tmp_path / "s2").exists()
    assert output_files(tmp_path) == ["f"]


def test_set_password_prompted_once_at_quiescence(tmp_path):
    asked = []

    def prompt(path):
        asked.append(os.path.basename(path))
        return "s"

    write(tmp_path / "A.7z", archive({"X.7z.001": volume("S1", 1, 2, {"f": "f"}, "s")}))
    write(tmp_path / "B.7z", archive({"X.7z.002": volume("S1", 2, 2, password="s")}))
    result, _ = run_pool(tmp_path, prompt=prompt)
    assert asked == ["X.7z.001"]
    assert output_files(tmp_path) == ["X/f"]
    assert result.unresolved == []


def test_set_password_ref_comes_from_extraction_when_probe_cannot_tell(tmp_path):
    class ReadableHeadersEngine(FakeEngine):
        def probe(self, archive_path, password=None):
            outcome = super().probe(archive_path, password)
            if outcome.ok and password is None:
                return wp.Outcome("ok", None, None, volumes=outcome.volumes)
            return outcome

    write(tmp_path / "X.7z.001", volume("S", 1, 2, {"f": "f"}, password="p2"))
    write(tmp_path / "X.7z.002", volume("S", 2, 2, password="p2"))
    result, _ = run_pool(tmp_path, engine=ReadableHeadersEngine(["p1", "p2"]))
    primary = next(i for i in result.items if i.name == "X.7z.001")
    assert primary.state is wp.State.CONSUMED
    assert primary.password_ref == 2


def test_learned_password_retries_deferred_sets_without_asking_again(tmp_path):
    asked = []

    def prompt(path):
        asked.append(os.path.basename(path))
        return "s"

    for name in ("A", "B"):
        write(tmp_path / f"{name}.7z.001", volume(name, 1, 2, {name: name}, "s"))
        write(tmp_path / f"{name}.7z.002", volume(name, 2, 2, password="s"))
    result, _ = run_pool(tmp_path, prompt=prompt)
    assert asked == ["A.7z.001"]
    assert output_files(tmp_path) == ["A", "B"]
    assert result.unresolved == []


def test_extraction_password_failure_qualifies_the_set_for_a_prompt(tmp_path):
    class ReadableHeadersEngine(FakeEngine):
        """Headers list without a password; only the payload is encrypted."""

        def probe(self, archive_path, password=None):
            if password is not None:
                return super().probe(archive_path, password)
            data = self._load(archive_path)
            secret = data.get("password") if isinstance(data, dict) else None
            outcome = super().probe(archive_path, secret or "")
            if outcome.ok:
                return wp.Outcome("ok", None, None, volumes=outcome.volumes)
            return outcome

    asked = []

    def prompt(path):
        asked.append(os.path.basename(path))
        return "p"

    write(tmp_path / "X.7z.001", volume("S", 1, 2, {"f": "f"}, password="p"))
    write(tmp_path / "X.7z.002", volume("S", 2, 2, password="p"))
    result, _ = run_pool(tmp_path, engine=ReadableHeadersEngine(), prompt=prompt)
    assert asked == ["X.7z.001"]
    assert output_files(tmp_path) == ["f"]


def test_attempt_cap(tmp_path):
    write(tmp_path / "A.7z", archive({"X.7z.001": volume("S1", 1, 2, {"f": "f"})}))
    write(tmp_path / "B.7z", archive({"X.7z.002": volume("S9", 2, 2)}))
    write(tmp_path / "C.7z", archive({"X.7z.002": volume("S8", 2, 2)}))
    result, _ = run_pool(tmp_path, max_attempts=2)
    reasons = {os.path.basename(i.path): i.reason for i in result.unresolved}
    assert reasons["X.7z.001"] == "too many combinations"


def test_results_do_not_depend_on_source_order(tmp_path):
    for case in ("one", "two"):
        root = tmp_path / case
        write(root / "A.7z", archive({"X.7z.002": volume("S1", 2, 2)}))
        write(root / "B.rar", archive({"X.7z.001": volume("S1", 1, 2, {"m": "m"})}))
    sources_one = [str(tmp_path / "one" / n) for n in ("A.7z", "B.rar")]
    sources_two = [str(tmp_path / "two" / n) for n in ("B.rar", "A.7z")]
    result_one, _ = run_pool(tmp_path / "one", sources=sources_one)
    result_two, _ = run_pool(tmp_path / "two", sources=sources_two)
    assert output_files(tmp_path / "one") == output_files(tmp_path / "two")
    assert deleted(result_one) == deleted(result_two)


# ------------------------------
# Parity with the old flow (openspec/.../parity.md)
# ------------------------------


def test_parity_p3_spanned_zip_inside_one_container(tmp_path):
    write(
        tmp_path / "A.7z",
        archive(
            {
                "X.zip": volume("Z", 1, 2, {"z.txt": "z"}),
                "X.z01": volume("Z", 2, 2),
            }
        ),
    )
    result, _ = run_pool(tmp_path)
    assert output_files(tmp_path) == ["X/z.txt"]
    assert deleted(result) == ["A.7z"]


@pytest.mark.parametrize(
    "primary, continuation",
    [
        ("X.rar", "X.r00"),
        ("X.zip", "X.z01"),
        ("X.zipx", "X.zx01"),
        ("X.arj", "X.a01"),
        ("X.ace", "X.c00"),
        ("X.part1.rar", "X.part2.rar"),
        ("X.tar.gz.001", "X.tar.gz.002"),
        ("X.zip.001", "X.zip.002"),
    ],
)
def test_parity_p8_continuation_in_another_container(tmp_path, primary, continuation):
    write(tmp_path / "A.7z", archive({primary: volume("S", 1, 2, {"f": "f"})}))
    write(tmp_path / "B.7z", archive({continuation: volume("S", 2, 2)}))
    result, _ = run_pool(tmp_path)
    assert output_files(tmp_path) == ["X/f"]
    assert deleted(result) == ["A.7z", "B.7z"]
    assert result.unresolved == []


def test_parity_p13_meaningless_leading_folders_are_flattened(tmp_path):
    write(tmp_path / "A.7z", archive({"1/5555+/222.jpg": "x", "photos/1/a.jpg": "a"}))
    run_pool(tmp_path)
    assert output_files(tmp_path) == ["222.jpg", "photos/1/a.jpg"]


def test_standalone_zip_with_unrelated_continuation(tmp_path):
    write(tmp_path / "X.zip", archive({"inside.txt": "i"}))
    write(tmp_path / "X.z01", volume("Q", 2, 2))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["inside.txt"]
    assert deleted(result) == ["X.zip"]
    assert (tmp_path / "X.z01").exists()
    assert [os.path.basename(i.path) for i in result.unresolved] == ["X.z01"]


def test_extra_unrelated_volume_is_dropped_from_the_combination(tmp_path):
    write(tmp_path / "X.part1.rar", volume("S", 1, 2, {"f": "f"}))
    write(tmp_path / "X.part2.rar", volume("S", 2, 2))
    write(tmp_path / "X.part3.rar", volume("OTHER", 3, 3))
    result, remover = run_pool(tmp_path)
    assert output_files(tmp_path) == ["f"]
    assert deleted(result) == ["X.part1.rar", "X.part2.rar"]
    assert [os.path.basename(i.path) for i in result.unresolved] == ["X.part3.rar"]


@pytest.mark.parametrize("name", ["X.part1.rar", "X.zip.001"])
def test_complete_source_set_in_one_folder_is_assembled_in_place(tmp_path, name):
    parsed = ma.parse_volume_name(name)
    second = name.replace(".part1.", ".part2.").replace(".001", ".002")
    write(tmp_path / name, volume("S", 1, 2, {"f": "f"}))
    write(tmp_path / second, volume("S", 2, 2))
    relocations = wp.MemoryRelocationLog()
    result, remover = run_pool(tmp_path, relocations=relocations)
    assert parsed is not None
    assert relocations.recorded == []
    assert deleted(result) == sorted([name, second])
    assert result.unresolved == []


def test_leftover_work_dirs_are_listed(tmp_path):
    (tmp_path / "temp.deepunzip-old1").mkdir()
    (tmp_path / "temp.deepunzip-note.txt").write_text("not a dir")
    (tmp_path / "other").mkdir()
    assert wp.leftover_work_dirs(str(tmp_path)) == [
        str(tmp_path / "temp.deepunzip-old1")
    ]


@pytest.mark.parametrize("name", ["X.rar", "X.zip", "X.zipx", "X.arj", "X.ace"])
def test_parity_p14_standalone_ambiguous_primary_is_a_container(tmp_path, name):
    write(tmp_path / name, archive({"inside.txt": "i"}))
    result, _ = run_pool(tmp_path)
    assert output_files(tmp_path) == ["inside.txt"]
    assert deleted(result) == [name]
    item = next(i for i in result.items if i.name == name)
    assert item.kind is wp.Kind.CONTAINER


def test_pool_announces_each_item_and_counts_rounds(tmp_path):
    events = []
    write(tmp_path / "A.7z", archive({"B.zip": archive({"c.txt": "c"})}))
    run_pool(tmp_path, emit=events.append)
    started = [
        os.path.basename(e.item.path) for e in events if isinstance(e, wp.ItemStarted)
    ]
    assert started == ["A.7z", "B.zip"]
    rounds = [
        (e.number, e.done, e.pending) for e in events if isinstance(e, wp.RoundStarted)
    ]
    assert rounds[:2] == [(1, 0, 1), (2, 1, 1)]


def test_set_attempt_is_announced_before_assembly(tmp_path):
    events = []
    write(tmp_path / "X.7z.001", volume("S", 1, 2, {"f": "f"}))
    write(tmp_path / "X.7z.002", volume("S", 2, 2))
    run_pool(tmp_path, emit=events.append)
    kinds = [type(e).__name__ for e in events if not isinstance(e, wp.RoundStarted)]
    assert kinds.index("ItemStarted") < kinds.index("SetAssembled")
