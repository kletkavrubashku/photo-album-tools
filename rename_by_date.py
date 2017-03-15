import argparse
import exifread
import prettytable
from datetime import datetime, timedelta
from glob import glob
from os import path, mkdir, rename
from shutil import copyfile


def get_date(fpath, *, noexcept=False):
    f = open(fpath, 'rb')
    tags = exifread.process_file(f, stop_tag="DateTime", details=False)
    dt = tags.get("Image DateTime", None)
    if not dt:
        exc = Exception("file '{}' has not info about datetime".format(path))
        if not noexcept:
            raise exc
        print(exc)
        return None
    return datetime.strptime(str(dt), "%Y:%m:%d %H:%M:%S")


def move_date(date, seconds):
    return date + timedelta(seconds=seconds)


def generate_fname(dt, *, ext="", num=0):
    suffix = " ({})".format(num) if num else ""
    extension = "{}".format(ext.lower()) if ext else ""
    return dt.strftime("IMG_%Y%m%d_%H%M%S" + suffix + extension)


def pick_path(dt, dirpath, *, ext=""):
    num = 0
    res = None
    while not num or path.exists(res):
        res = path.join(dirpath, generate_fname(dt, ext=ext, num=num))
        num += 1
    return res


def ask(msg):
    while True:
        choice = input("{} [yes/no]\n".format(msg)).lower()
        if choice in ['yes', 'y', 'ye']:
            return True
        elif choice in ['no', 'n', '']:
            return False


def describe_result(data, *, show_new_date=True):
    columns = ["file", "date", "new date", "new file"]
    if not show_new_date:
        del columns[2]

    pretty = prettytable.PrettyTable(columns)
    for row in data:
        if show_new_date:
            pretty.add_row(row)
        else:
            pretty.add_row([row[0], row[1], row[3]])
    return pretty


def excluded_files(dirpath, included_files):
    all_files = glob(path.join(dirpath, "*"))
    return list(set(all_files) - set(included_files))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-path", help="path to file/folder", required=True)
    parser.add_argument("--out-path", help="path to file/folder")
    parser.add_argument("--mask", default="*", help="mask 0f files")
    parser.add_argument("--delta", type=int, default=0, help="diff in seconds")
    parser.add_argument("--noexcept", default=False, action='store_true', help="skip exceptions")
    args = parser.parse_args()

    if not path.exists(args.in_path):
        raise Exception("path '{}' not exists".format(args.path))
    args.out_path = args.out_path if args.out_path else args.in_path
    if not path.exists(args.out_path):
        mkdir(args.out_path)

    files = []
    if path.isdir(args.in_path):
        files += glob(path.join(args.in_path, args.mask))
    else:
        files.append(args.in_path)
    files.sort()

    result = []
    for f in files:
        if path.isdir(f):
            continue
        _, ext = path.splitext(f)
        date = get_date(f, noexcept=args.noexcept)
        new_date = date
        new_fpath = path.join(args.out_path, path.basename(f))
        if date:
            new_date = move_date(date, args.delta)
            new_fpath = pick_path(new_date, args.out_path, ext=ext)

        result.append((f, date, new_date, new_fpath))

    table = describe_result(result, show_new_date=args.delta)
    print("Found files:\n{}".format(table))

    if not len(result):
        return

    if path.abspath(args.in_path) == path.abspath(args.out_path):
        if not ask("Rename found files?"):
            print("Exit")
            return

        for f in result:
            rename(f[0], f[3])
        print("All files is renamed!")
    else:
        if not ask("Copy found files?"):
            print("Exit")
            return

        copy_other_files = True
        other_files = excluded_files(args.in_path, [row[0] for row in result])
        if other_files:
            print("Other files:\n{}".format("\t{}".format('\n\t'.join(other_files))))
            copy_other_files = ask("Copy other files?")

        for f in result:
            copyfile(f[0], f[3])

        if copy_other_files:
            for f in other_files:
                copyfile(f, path.join(args.out_path, path.basename(f)))
            print("All files is copied!")
        else:
            print("Only selected files is copied!")


if __name__ == "__main__":
    main()
