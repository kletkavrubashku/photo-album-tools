import argparse
import exifread
import glob
import prettytable
from os import path


def get_date(path, *, force=False):
    f = open(path, 'rb')
    tags = exifread.process_file(f, stop_tag="DateTime", details=False)
    dt = tags.get("Image DateTime", None)
    if not dt:
        exc = Exception("file '{}' has not info about datetime".format(path))
        if not force:
            raise exc
        print(exc)
    return dt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", help="path to file/folder", required=True)
    parser.add_argument("--mask", default="*.JPG", help="mask 0f files")
    parser.add_argument("--diff", help="diff in seconds")
    parser.add_argument("--force", default=False, help="skip exceptions")
    args = parser.parse_args()

    if not path.exists(args.path):
        raise Exception("path '{}' not exists".format(args.path))

    files = []
    if path.isdir(args.path):
        files += glob.glob(path.join(args.path, args.mask))
    else:
        files.append(args.path)
    files.sort()

    files_and_dates = []
    pretty = prettytable.PrettyTable(["path", "date"])
    for f in files:
        date = get_date(f, force=args.force)
        pretty.add_row([f, date])
        files_and_dates.append((f, date))


    print("Found files:")
    print(pretty)


if __name__ == "__main__":
    main()