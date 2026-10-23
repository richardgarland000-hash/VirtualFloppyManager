from dropfiles import pick_image


def test_single_file(tmp_path):
    f = tmp_path / "a.img"
    f.write_bytes(b"x")
    assert pick_image([str(f)]) == (str(f), None, "info")


def test_several_files_uses_first_and_warns(tmp_path):
    a, b = tmp_path / "a.img", tmp_path / "b.img"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    path, message, kind = pick_image([str(a), str(b)])
    assert path == str(a) and kind == "warn" and "a.img" in message


def test_folder_rejected(tmp_path):
    path, message, kind = pick_image([str(tmp_path)])
    assert path is None and kind == "warn" and "folder" in message


def test_folder_plus_file_takes_the_file(tmp_path):
    f = tmp_path / "a.img"
    f.write_bytes(b"x")
    assert pick_image([str(tmp_path), str(f)])[0] == str(f)


def test_empty_drop():
    path, message, kind = pick_image([])
    assert path is None and kind == "warn"
