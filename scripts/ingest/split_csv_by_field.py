#!/usr/bin/env python3
"""
Split a CSV into multiple CSV files by the value of a specified column (field).
Idempotent and repeatable: output files are overwritten.
Usage:
  python scripts/ingest/split_csv_by_field.py data/questions/interview_questions.csv --field language --outdir data/questions
"""
import argparse
import csv
import os
import re
import io
import sys
try:
    from pathlib import Path
except Exception:
    Path = None


def slugify(s):
    if isinstance(s, bytes):
        try:
            s = s.decode('utf-8')
        except Exception:
            s = s.decode('latin-1', 'ignore')
    s = (s or 'unknown').strip()
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s or 'unknown'


def _is_py2():
    return sys.version_info[0] < 3


def _force_py2_dialect_bytes(dialect):
    """Python 2's csv module requires byte-string delimiters/quotechars."""
    if not _is_py2() or dialect is None:
        return dialect
    for attr in ('delimiter', 'quotechar', 'escapechar', 'lineterminator'):
        if hasattr(dialect, attr):
            val = getattr(dialect, attr)
            if isinstance(val, unicode):  # noqa: F821 (py2 only)
                try:
                    setattr(dialect, attr, val.encode('utf-8'))
                except Exception:
                    setattr(dialect, attr, val.encode('latin-1', 'ignore'))
    return dialect


def split_csv(input_path, field='language', out_dir='data/questions', encoding='utf-8'):
    if Path:
        out_dir_path = Path(out_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)
    else:
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
    writers = {}
    files = {}

    if _is_py2():
        # Python 2 csv expects bytes; open in binary.
        inf = open(input_path, 'rb')
        try:
            sample = inf.read(8192)
            inf.seek(0)
            dialect = None
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample)
            except Exception:
                dialect = csv.excel
            dialect = _force_py2_dialect_bytes(dialect)
            reader = csv.DictReader(inf, dialect=dialect)
        except Exception:
            inf.close()
            raise
    else:
        # Python 3: text mode with encoding.
        inf = io.open(input_path, 'r', encoding=encoding, newline='')
        # detect delimiter using csv.Sniffer if possible
        sample = inf.read(8192)
        inf.seek(0)
        dialect = None
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample)
        except Exception:
            dialect = csv.excel
        reader = csv.DictReader(inf, dialect=dialect)

    try:
        # Normalize fieldnames: handle Python2 bytes and malformed single-field header
        fnames = reader.fieldnames or []
        # decode bytes in py2
        norm_fnames = []
        for f in fnames:
            if isinstance(f, bytes):
                try:
                    norm_fnames.append(f.decode(encoding))
                except Exception:
                    norm_fnames.append(f.decode('latin-1', 'ignore'))
            else:
                norm_fnames.append(f)

        # if header was read as a single comma-joined field, split it
        if len(norm_fnames) == 1 and ',' in norm_fnames[0]:
            header_line = norm_fnames[0]
            split_names = [h.strip().strip('"').strip("'") for h in header_line.split(',')]
            reader.fieldnames = split_names
            norm_fnames = split_names

        if field not in norm_fnames:
            raise SystemExit("Field '{}' not found in CSV header: {}".format(field, norm_fnames))

        for row in reader:
            # Normalize and map language values to three buckets: java, php, magento
            raw_val = row.get(field) or ''
            if isinstance(raw_val, bytes):
                try:
                    raw_val = raw_val.decode(encoding)
                except Exception:
                    raw_val = raw_val.decode('latin-1', 'ignore')
            norm = (raw_val or '').strip().lower()
            if field == 'language':
                if 'Java' in norm:
                    key = 'Java'
                elif 'PHP' in norm:
                    key = 'PHP'
                elif 'Magento' in norm:
                    key = 'Magento'
                else:
                    # skip rows that are not one of the three target languages
                    continue
            else:
                key = raw_val or 'unknown'

            filename = "interview_questions_{}.csv".format(slugify(key))
            if Path and isinstance(out_dir, Path):
                out_path = out_dir / filename
            else:
                out_path = os.path.join(out_dir, filename)
            if key not in writers:
                # Python 2 csv expects binary; Python 3 can use text.
                if _is_py2():
                    f = open(out_path, 'wb')
                else:
                    f = io.open(out_path, 'w', encoding=encoding, newline='')

                # Prepare kwargs for DictWriter: ensure escapechar exists (avoid csv.Error)
                writer_kwargs = {}
                try:
                    esc_char = getattr(dialect, 'escapechar', None)
                except Exception:
                    esc_char = None

                if not esc_char:
                    # provide a default escapechar; use bytes on Py2, str on Py3
                    writer_kwargs['escapechar'] = b'\\' if _is_py2() else '\\'

                writer = csv.DictWriter(f, fieldnames=reader.fieldnames, dialect=dialect, **writer_kwargs)
                writer.writeheader()
                writers[key] = writer
                files[key] = f
            # sanitize row to match writer.fieldnames to avoid extra-field errors
            try:
                safe_row = {fn: row.get(fn, '') for fn in reader.fieldnames}
            except Exception:
                # fallback: filter keys that are in fieldnames
                safe_row = {}
                for k, v in row.items():
                    if k in reader.fieldnames:
                        safe_row[k] = v
            writers[key].writerow(safe_row)
    finally:
        try:
            inf.close()
        except Exception:
            pass

        # close output files
        for f in files.values():
            try:
                f.close()
            except Exception:
                pass


def main():
    p = argparse.ArgumentParser(description='Split CSV by field into separate CSV files.')
    p.add_argument('input', help='Input CSV file path')
    p.add_argument('--field', default='language', help='Field/column name to split by')
    p.add_argument('--outdir', default='data/questions', help='Output directory')
    p.add_argument('--encoding', default='utf-8', help='File encoding')
    args = p.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        raise SystemExit("Input file not found: {}".format(input_path))

    split_csv(input_path, field=args.field, out_dir=args.outdir, encoding=args.encoding)
    print("Split complete. Output files written to: {}".format(args.outdir))


if __name__ == '__main__':
    main()
