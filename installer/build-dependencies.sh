#!/bin/sh
set -eu
set --
for flag in "$LITEKB_MEDIA_NODES" "$LITEKB_EXTENDED_PROVIDERS" "$LITEKB_LOCAL_MODEL"; do
    case "$flag" in 0|1) ;; *) echo 'Use 0 or 1 for LiteKB build options.' >&2; exit 2 ;; esac
done
if [ "$LITEKB_MEDIA_NODES" = 1 ]; then set -- "$@" --extra media; fi
if [ "$LITEKB_EXTENDED_PROVIDERS" = 1 ]; then set -- "$@" --extra extended-providers; fi
if [ "$LITEKB_LOCAL_MODEL" = 1 ]; then set -- "$@" --extra local-model; fi

python -m venv /opt/py3
uv pip install --python /opt/py3/bin/python -r pyproject.toml "$@"
uv pip check --python /opt/py3/bin/python
uv pip install --python /opt/py3/bin/python --target /build/sandbox/python-packages requests pymysql psycopg2-binary
/opt/py3/bin/python -c "import tiktoken; [tiktoken.get_encoding(n) for n in ('cl100k_base', 'o200k_base')]"
